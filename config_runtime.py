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
