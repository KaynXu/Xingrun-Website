#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.resolve()
CFG_PATH = BASE_DIR / "config.json"

ENV_VAR_MAP = {
    "db_path": "XR_DB_PATH",
    "provider": "XR_PROVIDER",
    "review_plan_provider": "XR_REVIEW_PLAN_PROVIDER",
    "review_plan_model": "XR_REVIEW_PLAN_MODEL",
    "review_plan_reasoning_effort": "XR_REVIEW_PLAN_REASONING_EFFORT",
    "review_plan_temperature": "XR_REVIEW_PLAN_TEMPERATURE",
    "review_plan_writer_provider": "XR_REVIEW_PLAN_WRITER_PROVIDER",
    "review_plan_writer_model": "XR_REVIEW_PLAN_WRITER_MODEL",
    "review_plan_writer_temperature": "XR_REVIEW_PLAN_WRITER_TEMPERATURE",
    "review_plan_repair_temperature": "XR_REVIEW_PLAN_REPAIR_TEMPERATURE",
    "review_plan_reviewer_temperature": "XR_REVIEW_PLAN_REVIEWER_TEMPERATURE",
    "class_commentary_provider": "XR_CLASS_COMMENTARY_PROVIDER",
    "class_commentary_model": "XR_CLASS_COMMENTARY_MODEL",
    "class_commentary_openai_api_key": "XR_CLASS_COMMENTARY_OPENAI_API_KEY",
    "class_commentary_openai_base_url": "XR_CLASS_COMMENTARY_OPENAI_BASE_URL",
    "class_commentary_openai_headers": "XR_CLASS_COMMENTARY_OPENAI_HEADERS",
    "class_commentary_memory_enabled": "XR_CLASS_COMMENTARY_MEMORY_ENABLED",
    "class_commentary_structured_feedback_enabled": "XR_CLASS_COMMENTARY_STRUCTURED_FEEDBACK_ENABLED",
    "class_commentary_student_memory_v2_enabled": "XR_CLASS_COMMENTARY_STUDENT_MEMORY_V2_ENABLED",
    "redis_url": "XR_REDIS_URL",
    "class_commentary_memory_queue": "XR_CLASS_COMMENTARY_MEMORY_QUEUE",
    "class_commentary_memory_extraction_timeout": "XR_CLASS_COMMENTARY_MEMORY_EXTRACTION_TIMEOUT",
    "class_commentary_memory_operation_timeout": "XR_CLASS_COMMENTARY_MEMORY_OPERATION_TIMEOUT",
    "class_commentary_memory_reconcile_interval": "XR_CLASS_COMMENTARY_MEMORY_RECONCILE_INTERVAL",
    "mem0_vector_provider": "XR_MEM0_VECTOR_PROVIDER",
    "mem0_qdrant_url": "XR_MEM0_QDRANT_URL",
    "mem0_qdrant_api_key": "XR_MEM0_QDRANT_API_KEY",
    "mem0_collection_name": "XR_MEM0_COLLECTION_NAME",
    "mem0_embedder_provider": "XR_MEM0_EMBEDDER_PROVIDER",
    "mem0_embedder_model": "XR_MEM0_EMBEDDER_MODEL",
    "mem0_embedder_api_key": "XR_MEM0_EMBEDDER_API_KEY",
    "mem0_embedder_base_url": "XR_MEM0_EMBEDDER_BASE_URL",
    "mem0_embedding_dims": "XR_MEM0_EMBEDDING_DIMS",
    "mem0_style_limit": "XR_MEM0_STYLE_LIMIT",
    "mem0_student_limit": "XR_MEM0_STUDENT_LIMIT",
    "mem0_context_char_limit": "XR_MEM0_CONTEXT_CHAR_LIMIT",
    "skill_evolution_min_effective_tasks": "XR_SKILL_EVOLUTION_MIN_EFFECTIVE_TASKS",
    "skill_evolution_min_support_tasks": "XR_SKILL_EVOLUTION_MIN_SUPPORT_TASKS",
    "skill_evolution_build_timeout": "XR_SKILL_EVOLUTION_BUILD_TIMEOUT",
    "review_plan_langfuse_enabled": "XR_REVIEW_PLAN_LANGFUSE_ENABLED",
    "langfuse_public_key": "LANGFUSE_PUBLIC_KEY",
    "langfuse_secret_key": "LANGFUSE_SECRET_KEY",
    "langfuse_base_url": "LANGFUSE_BASE_URL",
    "openai_api_key": "OPENAI_API_KEY",
    "openai_model": "XR_OPENAI_MODEL",
    "openai_base_url": "XR_OPENAI_BASE_URL",
    "deepseek_api_key": "DEEPSEEK_API_KEY",
    "deepseek_model": "XR_DEEPSEEK_MODEL",
    "qwen_api_key": "DASHSCOPE_API_KEY",
    "qwen_base_url": "XR_QWEN_BASE_URL",
    "vision_provider": "XR_VISION_PROVIDER",
    "vision_model": "XR_VISION_MODEL",
    "admin_username": "XR_ADMIN_USERNAME",
    "admin_password_hash": "XR_ADMIN_PASSWORD_HASH",
    "wrong_question_service_url": "XR_WRONG_QUESTION_SERVICE_URL",
    "wrong_question_service_token": "XR_WRONG_QUESTION_SERVICE_TOKEN",
    "wechat_service_token": "XR_WECHAT_SERVICE_TOKEN",
    "colleague_skill_dir": "XR_COLLEAGUE_SKILL_DIR",
    "audio_transcription_provider": "XR_AUDIO_TRANSCRIPTION_PROVIDER",
    "tencentcloud_secret_id": "TENCENTCLOUD_SECRET_ID",
    "tencentcloud_secret_key": "TENCENTCLOUD_SECRET_KEY",
    "tencentcloud_app_id": "TENCENTCLOUD_APP_ID",
    "tencent_asr_engine_type": "XR_TENCENT_ASR_ENGINE_TYPE",
    "xhs_app_id": "XHS_APP_ID",
    "xhs_app_secret": "XHS_APP_SECRET",
}

DEFAULTS = {
    "provider": "deepseek",
    "review_plan_provider": "",
    "review_plan_model": "",
    "review_plan_reasoning_effort": "",
    "review_plan_temperature": 0.25,
    "review_plan_writer_provider": "deepseek",
    "review_plan_writer_model": "",
    "review_plan_writer_temperature": 0.35,
    "review_plan_repair_temperature": 0.1,
    "review_plan_reviewer_temperature": 0.1,
    "class_commentary_provider": "",
    "class_commentary_model": "",
    "class_commentary_openai_api_key": "",
    "class_commentary_openai_base_url": "",
    "class_commentary_openai_headers": "",
    "class_commentary_memory_enabled": False,
    "class_commentary_structured_feedback_enabled": False,
    "class_commentary_student_memory_v2_enabled": False,
    "redis_url": "redis://127.0.0.1:6379/0",
    "class_commentary_memory_queue": "class_commentary_memory",
    "class_commentary_memory_extraction_timeout": 300,
    "class_commentary_memory_operation_timeout": 120,
    "class_commentary_memory_reconcile_interval": 600,
    "mem0_vector_provider": "qdrant",
    "mem0_qdrant_url": "",
    "mem0_qdrant_api_key": "",
    "mem0_collection_name": "xingrun_class_commentary_memory",
    "mem0_embedder_provider": "",
    "mem0_embedder_model": "",
    "mem0_embedder_api_key": "",
    "mem0_embedder_base_url": "",
    "mem0_embedding_dims": 0,
    "mem0_style_limit": 8,
    "mem0_student_limit": 5,
    "mem0_context_char_limit": 3000,
    "skill_evolution_min_effective_tasks": 5,
    "skill_evolution_min_support_tasks": 3,
    "skill_evolution_build_timeout": 300,
    "review_plan_langfuse_enabled": False,
    "langfuse_public_key": "",
    "langfuse_secret_key": "",
    "langfuse_base_url": "",
    "openai_model": "gpt-4o",
    "openai_base_url": "",
    "xhs_base_url": "https://ark.xiaohongshu.com",
    "qwen_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "vision_provider": "qwen",
    "vision_model": "qwen-vl-max-latest",
    "deepseek_model": "deepseek-v4-pro",
    "wrong_question_service_url": "",
    "wrong_question_service_token": "",
    "wechat_service_token": "",
    "colleague_skill_dir": "",
    "audio_transcription_provider": "local",
    "tencent_asr_engine_type": "16k_zh",
}


def load_file_config() -> dict:
    if CFG_PATH.exists():
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def write_file_config(cfg: dict) -> None:
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_env_overrides() -> dict:
    overrides = {}
    for key, env_name in ENV_VAR_MAP.items():
        value = os.environ.get(env_name)
        if value is not None and value.strip():
            overrides[key] = value.strip()
    return overrides


def env_controlled_keys() -> set[str]:
    return set(get_env_overrides().keys())


def env_var_for_key(key: str) -> Optional[str]:
    return ENV_VAR_MAP.get(key)


def normalize_chat_provider(value: object) -> str:
    provider = str(value or "").strip().lower()
    if provider == "openai":
        return "openai"
    return "deepseek"


def normalize_optional_chat_provider(value: object) -> str:
    provider = str(value or "").strip()
    if not provider:
        return ""
    return normalize_chat_provider(provider)


def normalize_reasoning_effort(value: object) -> str:
    effort = str(value or "").strip().lower()
    if effort in {"low", "medium", "high"}:
        return effort
    return ""


def normalize_bool_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    flag = str(value or "").strip().lower()
    return flag in {"1", "true", "yes", "on", "enabled"}


def normalize_temperature(value: object, default: float = 0.3) -> float:
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return float(default)
    if temperature < 0:
        return 0.0
    if temperature > 2:
        return 2.0
    return temperature


def normalize_positive_int(value: object, default: int, *, allow_zero: bool = False) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return int(default)
    minimum = 0 if allow_zero else 1
    if normalized < minimum:
        return int(default)
    return normalized


def normalize_vision_provider(value: object) -> str:
    provider = str(value or "").strip().lower()
    if provider == "openai":
        return "openai"
    return "qwen"


def normalize_audio_transcription_provider(value: object) -> str:
    provider = str(value or "").strip().lower()
    if provider == "tencent":
        return "tencent"
    return "local"


def get_runtime_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(load_file_config())
    cfg.update(get_env_overrides())
    cfg["provider"] = normalize_chat_provider(cfg.get("provider"))
    cfg["review_plan_provider"] = normalize_optional_chat_provider(cfg.get("review_plan_provider"))
    cfg["review_plan_model"] = str(cfg.get("review_plan_model") or "").strip()
    cfg["review_plan_reasoning_effort"] = normalize_reasoning_effort(cfg.get("review_plan_reasoning_effort"))
    cfg["review_plan_temperature"] = normalize_temperature(cfg.get("review_plan_temperature"), 0.25)
    cfg["review_plan_writer_provider"] = normalize_chat_provider(cfg.get("review_plan_writer_provider") or "deepseek")
    cfg["review_plan_writer_model"] = str(cfg.get("review_plan_writer_model") or "").strip()
    cfg["review_plan_writer_temperature"] = normalize_temperature(cfg.get("review_plan_writer_temperature"), 0.35)
    cfg["review_plan_repair_temperature"] = normalize_temperature(cfg.get("review_plan_repair_temperature"), 0.1)
    cfg["review_plan_reviewer_temperature"] = normalize_temperature(cfg.get("review_plan_reviewer_temperature"), 0.1)
    cfg["class_commentary_provider"] = normalize_optional_chat_provider(cfg.get("class_commentary_provider"))
    cfg["class_commentary_model"] = str(cfg.get("class_commentary_model") or "").strip()
    cfg["class_commentary_openai_api_key"] = str(cfg.get("class_commentary_openai_api_key") or "").strip()
    cfg["class_commentary_openai_base_url"] = str(cfg.get("class_commentary_openai_base_url") or "").strip()
    cfg["class_commentary_openai_headers"] = str(cfg.get("class_commentary_openai_headers") or "").strip()
    cfg["class_commentary_memory_enabled"] = normalize_bool_flag(
        cfg.get("class_commentary_memory_enabled")
    )
    cfg["class_commentary_structured_feedback_enabled"] = normalize_bool_flag(
        cfg.get("class_commentary_structured_feedback_enabled")
    )
    cfg["class_commentary_student_memory_v2_enabled"] = normalize_bool_flag(
        cfg.get("class_commentary_student_memory_v2_enabled")
    )
    cfg["redis_url"] = str(cfg.get("redis_url") or "redis://127.0.0.1:6379/0").strip()
    cfg["class_commentary_memory_queue"] = (
        str(cfg.get("class_commentary_memory_queue") or "class_commentary_memory").strip()
        or "class_commentary_memory"
    )
    cfg["class_commentary_memory_extraction_timeout"] = normalize_positive_int(
        cfg.get("class_commentary_memory_extraction_timeout"), 300
    )
    cfg["class_commentary_memory_operation_timeout"] = normalize_positive_int(
        cfg.get("class_commentary_memory_operation_timeout"), 120
    )
    cfg["class_commentary_memory_reconcile_interval"] = normalize_positive_int(
        cfg.get("class_commentary_memory_reconcile_interval"), 600
    )
    cfg["mem0_vector_provider"] = str(cfg.get("mem0_vector_provider") or "qdrant").strip() or "qdrant"
    cfg["mem0_qdrant_url"] = str(cfg.get("mem0_qdrant_url") or "").strip()
    cfg["mem0_qdrant_api_key"] = str(cfg.get("mem0_qdrant_api_key") or "").strip()
    cfg["mem0_collection_name"] = (
        str(cfg.get("mem0_collection_name") or "xingrun_class_commentary_memory").strip()
        or "xingrun_class_commentary_memory"
    )
    cfg["mem0_embedder_provider"] = str(cfg.get("mem0_embedder_provider") or "").strip()
    cfg["mem0_embedder_model"] = str(cfg.get("mem0_embedder_model") or "").strip()
    cfg["mem0_embedder_api_key"] = str(cfg.get("mem0_embedder_api_key") or "").strip()
    cfg["mem0_embedder_base_url"] = str(cfg.get("mem0_embedder_base_url") or "").strip()
    cfg["mem0_embedding_dims"] = normalize_positive_int(
        cfg.get("mem0_embedding_dims"), 0, allow_zero=True
    )
    cfg["mem0_style_limit"] = normalize_positive_int(cfg.get("mem0_style_limit"), 8)
    cfg["mem0_student_limit"] = normalize_positive_int(cfg.get("mem0_student_limit"), 5)
    cfg["mem0_context_char_limit"] = normalize_positive_int(
        cfg.get("mem0_context_char_limit"), 3000
    )
    cfg["skill_evolution_min_effective_tasks"] = normalize_positive_int(
        cfg.get("skill_evolution_min_effective_tasks"), 5
    )
    cfg["skill_evolution_min_support_tasks"] = normalize_positive_int(
        cfg.get("skill_evolution_min_support_tasks"), 3
    )
    cfg["skill_evolution_build_timeout"] = normalize_positive_int(
        cfg.get("skill_evolution_build_timeout"), 300
    )
    cfg["review_plan_langfuse_enabled"] = normalize_bool_flag(cfg.get("review_plan_langfuse_enabled"))
    cfg["langfuse_public_key"] = str(cfg.get("langfuse_public_key") or "").strip()
    cfg["langfuse_secret_key"] = str(cfg.get("langfuse_secret_key") or "").strip()
    cfg["langfuse_base_url"] = str(cfg.get("langfuse_base_url") or "").strip()
    cfg["openai_model"] = str(cfg.get("openai_model") or "gpt-4o").strip() or "gpt-4o"
    cfg["openai_base_url"] = str(cfg.get("openai_base_url") or "").strip()
    cfg["colleague_skill_dir"] = str(cfg.get("colleague_skill_dir") or "").strip()
    cfg["vision_provider"] = normalize_vision_provider(cfg.get("vision_provider"))
    cfg["audio_transcription_provider"] = normalize_audio_transcription_provider(
        cfg.get("audio_transcription_provider")
    )
    cfg["tencentcloud_secret_id"] = str(cfg.get("tencentcloud_secret_id") or "").strip()
    cfg["tencentcloud_secret_key"] = str(cfg.get("tencentcloud_secret_key") or "").strip()
    cfg["tencentcloud_app_id"] = str(cfg.get("tencentcloud_app_id") or "").strip()
    cfg["tencent_asr_engine_type"] = str(cfg.get("tencent_asr_engine_type") or "16k_zh").strip() or "16k_zh"
    return cfg


def chat_model_for_provider(provider: object, cfg: Optional[dict] = None) -> str:
    runtime = cfg or get_runtime_config()
    provider_name = normalize_chat_provider(provider)
    if provider_name == "deepseek":
        return str(runtime.get("deepseek_model") or "deepseek-v4-pro")
    return str(runtime.get("openai_model") or "gpt-4o")


def resolve_review_plan_provider(cfg: Optional[dict] = None) -> str:
    runtime = cfg or get_runtime_config()
    return normalize_chat_provider(runtime.get("review_plan_provider") or runtime.get("provider") or "deepseek")


def resolve_review_plan_model(cfg: Optional[dict] = None, provider: object = "") -> str:
    runtime = cfg or get_runtime_config()
    model = str(runtime.get("review_plan_model") or "").strip()
    if model:
        return model
    provider_name = normalize_chat_provider(provider or resolve_review_plan_provider(runtime))
    return chat_model_for_provider(provider_name, runtime)


def resolve_review_plan_writer_provider(cfg: Optional[dict] = None) -> str:
    runtime = cfg or get_runtime_config()
    return normalize_chat_provider(runtime.get("review_plan_writer_provider") or "deepseek")


def resolve_review_plan_writer_model(cfg: Optional[dict] = None, provider: object = "") -> str:
    runtime = cfg or get_runtime_config()
    model = str(runtime.get("review_plan_writer_model") or "").strip()
    if model:
        return model
    provider_name = normalize_chat_provider(provider or resolve_review_plan_writer_provider(runtime))
    if provider_name == "deepseek":
        return "deepseek-v4-pro"
    return chat_model_for_provider(provider_name, runtime)


def resolve_review_plan_reasoning_effort(cfg: Optional[dict] = None, provider: object = "") -> str:
    runtime = cfg or get_runtime_config()
    provider_name = normalize_chat_provider(provider or resolve_review_plan_provider(runtime))
    if provider_name != "openai":
        return ""
    return normalize_reasoning_effort(runtime.get("review_plan_reasoning_effort"))


def resolve_review_plan_temperature(cfg: Optional[dict] = None) -> float:
    runtime = cfg or get_runtime_config()
    return normalize_temperature(runtime.get("review_plan_temperature"), 0.25)


def resolve_review_plan_writer_temperature(cfg: Optional[dict] = None) -> float:
    runtime = cfg or get_runtime_config()
    return normalize_temperature(runtime.get("review_plan_writer_temperature"), 0.35)


def resolve_review_plan_repair_temperature(cfg: Optional[dict] = None) -> float:
    runtime = cfg or get_runtime_config()
    return normalize_temperature(runtime.get("review_plan_repair_temperature"), 0.1)


def resolve_review_plan_reviewer_temperature(cfg: Optional[dict] = None) -> float:
    runtime = cfg or get_runtime_config()
    return normalize_temperature(runtime.get("review_plan_reviewer_temperature"), 0.1)


def resolve_class_commentary_provider(cfg: Optional[dict] = None, fallback: object = "") -> str:
    runtime = cfg or get_runtime_config()
    return normalize_chat_provider(runtime.get("class_commentary_provider") or fallback or runtime.get("provider") or "deepseek")


def resolve_class_commentary_model(cfg: Optional[dict] = None, provider: object = "", fallback_model: object = "") -> str:
    runtime = cfg or get_runtime_config()
    model = str(runtime.get("class_commentary_model") or "").strip()
    if model:
        return model
    if fallback_model:
        return str(fallback_model)
    return chat_model_for_provider(provider or resolve_class_commentary_provider(runtime), runtime)
