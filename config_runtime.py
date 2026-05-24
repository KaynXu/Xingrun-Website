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
    "openai_api_key": "OPENAI_API_KEY",
    "deepseek_api_key": "DEEPSEEK_API_KEY",
    "deepseek_model": "XR_DEEPSEEK_MODEL",
    "mimo_api_key": "MIMO_API_KEY",
    "mimo_base_url": "XR_MIMO_BASE_URL",
    "mimo_model": "XR_MIMO_MODEL",
    "n1n_api_key": "N1N_API_KEY",
    "n1n_base_url": "XR_N1N_BASE_URL",
    "n1n_model": "XR_N1N_MODEL",
    "qwen_api_key": "DASHSCOPE_API_KEY",
    "qwen_base_url": "XR_QWEN_BASE_URL",
    "vision_provider": "XR_VISION_PROVIDER",
    "vision_model": "XR_VISION_MODEL",
    "admin_username": "XR_ADMIN_USERNAME",
    "admin_password_hash": "XR_ADMIN_PASSWORD_HASH",
    "wrong_question_service_url": "XR_WRONG_QUESTION_SERVICE_URL",
    "wrong_question_service_token": "XR_WRONG_QUESTION_SERVICE_TOKEN",
    "wechat_service_token": "XR_WECHAT_SERVICE_TOKEN",
    "xhs_app_id": "XHS_APP_ID",
    "xhs_app_secret": "XHS_APP_SECRET",
}

DEFAULTS = {
    "provider": "deepseek",
    "xhs_base_url": "https://ark.xiaohongshu.com",
    "mimo_model": "MiMo-7B-RL",
    "n1n_base_url": "https://api.n1n.ai/v1",
    "n1n_model": "gpt-4o",
    "qwen_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "vision_provider": "n1n",
    "vision_model": "gpt-5.5",
    "deepseek_model": "deepseek-chat",
    "wrong_question_service_url": "",
    "wrong_question_service_token": "",
    "wechat_service_token": "",
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


def get_runtime_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(load_file_config())
    cfg.update(get_env_overrides())
    return cfg
