#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from typing import Any

EXPECTED_VALUES = {
    "XR_AUDIO_TRANSCRIPTION_PROVIDER": "tencent",
    "XR_TENCENT_ASR_ENGINE_TYPE": "16k_zh",
    "XR_REVIEW_PLAN_PROVIDER": "openai",
    "XR_REVIEW_PLAN_MODEL": "gpt-5.5",
    "XR_REVIEW_PLAN_WRITER_PROVIDER": "deepseek",
    "XR_REVIEW_PLAN_WRITER_MODEL": "deepseek-v4-pro",
    "XR_CLASS_COMMENTARY_PROVIDER": "openai",
    "XR_CLASS_COMMENTARY_MODEL": "gpt-5.5",
}

CREDENTIAL_KEYS = (
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "TENCENTCLOUD_SECRET_ID",
    "TENCENTCLOUD_SECRET_KEY",
    "XR_CLASS_COMMENTARY_OPENAI_API_KEY",
    "XR_WRONG_QUESTION_SERVICE_TOKEN",
    "XR_WECHAT_SERVICE_TOKEN",
    "XR_ADMIN_PASSWORD_HASH",
    "XHS_APP_SECRET",
)


def _truthy(value: object) -> bool:
    return str(value or "").strip() != ""


def _load_pm2_env(service_name: str = "xingrun") -> dict[str, str]:
    try:
        completed = subprocess.run(
            ["pm2", "jlist"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {}

    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return {}

    for item in payload:
        pm2_env = item.get("pm2_env") or {}
        proc_name = str(pm2_env.get("name") or item.get("name") or "").strip()
        if service_name and proc_name != service_name:
            continue
        env = pm2_env.get("env") or {}
        if isinstance(env, dict) and env:
            return {str(key): str(value) for key, value in env.items() if value is not None}
    return {}


def load_runtime_env(source: str = "auto", service_name: str = "xingrun") -> tuple[str, dict[str, str]]:
    if source == "env":
        return "env", dict(os.environ)
    if source == "pm2":
        return "pm2", _load_pm2_env(service_name=service_name)

    pm2_env = _load_pm2_env(service_name=service_name)
    if pm2_env:
        return "pm2", pm2_env
    return "env", dict(os.environ)


def build_contract_report(env: Mapping[str, Any]) -> list[str]:
    lines = [f"{key}={env.get(key, '')}" for key in EXPECTED_VALUES]
    lines.extend(f"{key}_present={_truthy(env.get(key))}" for key in CREDENTIAL_KEYS)
    return lines


def validate_contract(env: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, expected in EXPECTED_VALUES.items():
        actual = str(env.get(key, "") or "").strip()
        if actual != expected:
            errors.append(f"{key} expected {expected!r} but got {actual!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    source = "auto"
    service_name = "xingrun"
    if args:
        source = args.pop(0)
    if args:
        service_name = args.pop(0)

    runtime_source, env = load_runtime_env(source=source, service_name=service_name)
    print(f"source={runtime_source}")
    for line in build_contract_report(env):
        print(line)

    errors = validate_contract(env)
    if errors:
        print("contract_ok=False")
        for error in errors:
            print(error)
        return 1

    print("contract_ok=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
