from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Optional, TypeVar

from config_runtime import (
    chat_model_for_provider,
    get_runtime_config,
    normalize_chat_provider,
    normalize_reasoning_effort,
    resolve_review_plan_model,
    resolve_review_plan_provider,
)
from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)
REVIEW_PLAN_LLM_TIMEOUT_SECONDS = 180.0


_BARE_LATEX_COMMAND_RE = re.compile(
    r"(?<!\\)\\(?:left|right|frac|sqrt|theta|alpha|beta|gamma|delta|pi|sin|cos|tan|"
    r"log|ln|angle|parallel|perp|cdot|times|div|leq|geq|neq|pm|circ|text|overline|widehat)\b"
)


def _escape_bare_backslashes_in_json_strings(raw: str) -> str:
    result: list[str] = []
    in_string = False
    i = 0
    valid_simple_escapes = {'"', "\\", "/", "b", "f", "n", "r", "t"}

    while i < len(raw):
        char = raw[i]
        if not in_string:
            result.append(char)
            if char == '"':
                in_string = True
            i += 1
            continue

        if char == '"':
            result.append(char)
            in_string = False
            i += 1
            continue

        if char != "\\":
            result.append(char)
            i += 1
            continue

        if i + 1 >= len(raw):
            result.append("\\\\")
            i += 1
            continue

        next_char = raw[i + 1]
        if next_char == "u" and i + 5 < len(raw) and re.fullmatch(r"[0-9a-fA-F]{4}", raw[i + 2 : i + 6]):
            result.append(raw[i : i + 6])
            i += 6
            continue
        if next_char in {'"', "\\", "/"}:
            result.append(raw[i : i + 2])
            i += 2
            continue
        if next_char in valid_simple_escapes and not (i + 2 < len(raw) and raw[i + 2].isalpha()):
            result.append(raw[i : i + 2])
            i += 2
            continue

        result.append("\\\\")
        i += 1

    return "".join(result)


def loads_model_json(raw: Optional[str], default: str = "{}") -> dict[str, Any]:
    content = raw if raw is not None and str(raw).strip() else default
    if _BARE_LATEX_COMMAND_RE.search(content):
        return json.loads(_escape_bare_backslashes_in_json_strings(content))
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = json.loads(_escape_bare_backslashes_in_json_strings(content))
    if not isinstance(data, dict):
        raise ValueError("model JSON response must be an object")
    return data


def _runtime_config() -> dict[str, Any]:
    return get_runtime_config()


def resolve_chat_provider(provider: str = "") -> str:
    if provider:
        return normalize_chat_provider(provider)
    return resolve_review_plan_provider(_runtime_config())


def resolve_chat_model(provider: str = "", model: str = "") -> str:
    cfg = _runtime_config()
    if model:
        return model
    provider_name = resolve_chat_provider(provider)
    if not provider:
        return resolve_review_plan_model(cfg, provider=provider_name)
    return chat_model_for_provider(provider_name, cfg)


def get_chat_client(provider: str = ""):
    from openai import OpenAI

    cfg = _runtime_config()
    provider_name = resolve_chat_provider(provider)

    if provider_name == "deepseek":
        key = cfg.get("deepseek_api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise RuntimeError("未找到 DeepSeek API Key，请在设置页面配置。")
        return OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")

    key = cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("未找到 OpenAI API Key，请在设置页面配置 openai_api_key，或设置环境变量 OPENAI_API_KEY。")
    base_url = str(cfg.get("openai_base_url") or "").strip()
    if base_url:
        return OpenAI(api_key=key, base_url=base_url)
    return OpenAI(api_key=key)


def usage_dict(response: Any, *, provider: str = "", model_fallback: str = "") -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    return {
        "provider": resolve_chat_provider(provider),
        "model": str(getattr(response, "model", "") or model_fallback or resolve_chat_model(provider)),
        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }


def merge_usage(*usages: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "provider": "",
        "model": "",
        "input_tokens": 0,
        "output_tokens": 0,
    }
    for usage in usages:
        if not isinstance(usage, dict):
            continue
        if not merged["provider"] and usage.get("provider"):
            merged["provider"] = str(usage.get("provider") or "")
        if not merged["model"] and usage.get("model"):
            merged["model"] = str(usage.get("model") or "")
        merged["input_tokens"] += max(0, int(usage.get("input_tokens", 0) or 0))
        merged["output_tokens"] += max(0, int(usage.get("output_tokens", 0) or 0))
    return merged


def generate_review_plan_json(
    *,
    system_prompt: str,
    user_message: str,
    provider: str = "",
    model: str = "",
    reasoning_effort: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    provider_name = resolve_chat_provider(provider)
    model_name = resolve_chat_model(provider_name, model)
    client = get_chat_client(provider_name)
    request_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "timeout": REVIEW_PLAN_LLM_TIMEOUT_SECONDS,
    }
    normalized_effort = normalize_reasoning_effort(reasoning_effort)
    if provider_name == "openai" and normalized_effort:
        request_kwargs["reasoning_effort"] = normalized_effort
    response = client.chat.completions.create(**request_kwargs)
    raw = response.choices[0].message.content
    return loads_model_json(raw), usage_dict(response, provider=provider_name, model_fallback=model_name)


def generate_structured(
    *,
    producer: Callable[[], dict[str, Any]],
    schema: type[ModelT],
    node_name: str,
) -> ModelT:
    """Validate a structured producer output with a Pydantic schema.

    The production LLM provider stays in ai_processor for Phase 1; this helper
    establishes the future boundary for node-level structured generation.
    """

    payload = producer()
    try:
        return schema.model_validate(payload)
    except Exception as exc:
        raise ValueError(f"{node_name} returned invalid structured output: {exc}") from exc
