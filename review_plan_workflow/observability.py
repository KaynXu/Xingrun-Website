from __future__ import annotations

import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from config_runtime import get_runtime_config


_LANGFUSE_CLIENT: Any | None = None
_SENSITIVE_KEY_PARTS = {
    "api_key",
    "authorization",
    "content",
    "message",
    "password",
    "prompt",
    "raw",
    "secret",
    "summary",
    "text",
    "token",
    "transcript",
}
_SAFE_PREVIEW_KEYS = {
    "date",
    "grade",
    "lesson_date",
    "model",
    "node_name",
    "provider",
    "reasoning_effort",
    "selected_subject",
    "status",
    "subject",
    "topic",
}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _text_summary(value: object, *, include_preview: bool = False, preview_chars: int = 80) -> dict[str, Any]:
    text = str(value or "")
    payload: dict[str, Any] = {
        "chars": len(text),
        "sha256": _hash_text(text) if text else "",
    }
    if include_preview:
        payload["preview"] = text[:preview_chars]
    return payload


def _safe_key(key: object) -> str:
    return str(key or "").strip().lower()


def _is_sensitive_key(key: object) -> bool:
    normalized = _safe_key(key)
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _is_safe_preview_key(key: object) -> bool:
    return _safe_key(key) in _SAFE_PREVIEW_KEYS


def summarize_for_observability(value: object, *, depth: int = 0) -> object:
    """Return a bounded, PII-conscious summary for trace inputs/outputs."""

    if hasattr(value, "model_dump"):
        try:
            value = value.model_dump()
        except Exception:
            return {"type": type(value).__name__}

    if isinstance(value, str):
        return _text_summary(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        sample = [summarize_for_observability(item, depth=depth + 1) for item in list(value)[:5]]
        return {"type": type(value).__name__, "count": len(value), "sample": sample}
    if isinstance(value, dict):
        keys = [str(key) for key in value.keys()]
        if depth >= 2:
            return {"type": "dict", "key_count": len(keys), "keys": keys[:20]}

        payload: dict[str, Any] = {
            "type": "dict",
            "key_count": len(keys),
            "keys": keys[:20],
        }
        fields: dict[str, Any] = {}
        for key, item in list(value.items())[:20]:
            key_text = str(key)
            if isinstance(item, str):
                fields[key_text] = _text_summary(item, include_preview=_is_safe_preview_key(key_text))
            elif _is_sensitive_key(key_text):
                fields[key_text] = summarize_for_observability(item, depth=2)
            else:
                fields[key_text] = summarize_for_observability(item, depth=depth + 1)
        if fields:
            payload["fields"] = fields
        return payload

    return {"type": type(value).__name__, "repr_hash": _hash_text(repr(value))}


def summarize_review_input(review_input: object) -> dict[str, Any]:
    if hasattr(review_input, "model_dump"):
        data = review_input.model_dump()
    elif isinstance(review_input, dict):
        data = review_input
    else:
        data = {}
    return {
        "subject": str(data.get("subject") or "")[:40],
        "grade": str(data.get("grade") or "")[:40],
        "topic": _text_summary(data.get("topic", ""), include_preview=True),
        "weak_points": _text_summary(data.get("weak_points", "")),
        "summary_text": _text_summary(data.get("summary_text", "")),
        "lesson_date": str(data.get("lesson_date") or "")[:40],
    }


def summarize_review_plan(plan: object) -> dict[str, Any]:
    data = plan if isinstance(plan, dict) else {}
    lesson_info = data.get("lesson_info") if isinstance(data.get("lesson_info"), dict) else {}
    days = data.get("days") if isinstance(data.get("days"), list) else []
    day_summaries = []
    for day in days[:10]:
        if not isinstance(day, dict):
            continue
        day_summaries.append(
            {
                "day": day.get("day"),
                "items": len(day.get("items") or []),
                "blanks": len(day.get("blanks") or []),
                "choices": len(day.get("choices") or []),
                "steps": len(day.get("steps") or []),
            }
        )
    return {
        "topic": _text_summary(lesson_info.get("topic", ""), include_preview=True),
        "subject": str(lesson_info.get("subject") or data.get("subject") or "")[:40],
        "grade": str(lesson_info.get("grade") or "")[:40],
        "day_count": len(days),
        "full_review_topics_count": len(data.get("full_review_topics") or []),
        "day_summaries": day_summaries,
        "weak_points_summary": _text_summary(data.get("weak_points_summary", "")),
    }


def summarize_usage(usage: object) -> dict[str, Any]:
    payload = usage if isinstance(usage, dict) else {}
    return {
        "provider": str(payload.get("provider") or ""),
        "model": str(payload.get("model") or ""),
        "input_tokens": max(0, int(payload.get("input_tokens", 0) or 0)),
        "output_tokens": max(0, int(payload.get("output_tokens", 0) or 0)),
    }


def review_plan_langfuse_enabled() -> bool:
    cfg = get_runtime_config()
    if not bool(cfg.get("review_plan_langfuse_enabled")):
        return False
    return bool(cfg.get("langfuse_public_key") and cfg.get("langfuse_secret_key"))


def _ensure_langfuse_env() -> None:
    cfg = get_runtime_config()
    public_key = str(cfg.get("langfuse_public_key") or "").strip()
    secret_key = str(cfg.get("langfuse_secret_key") or "").strip()
    base_url = str(cfg.get("langfuse_base_url") or os.environ.get("LANGFUSE_HOST") or "").strip()
    if public_key:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", public_key)
    if secret_key:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", secret_key)
    if base_url:
        os.environ.setdefault("LANGFUSE_BASE_URL", base_url)


def get_langfuse_client() -> Any | None:
    global _LANGFUSE_CLIENT
    if not review_plan_langfuse_enabled():
        return None
    if _LANGFUSE_CLIENT is not None:
        return _LANGFUSE_CLIENT

    _ensure_langfuse_env()
    try:
        from langfuse import get_client
    except Exception:
        return None

    try:
        _LANGFUSE_CLIENT = get_client()
    except Exception:
        return None
    return _LANGFUSE_CLIENT


def _safe_update(observation: object, **kwargs: Any) -> None:
    if observation is None:
        return
    update = getattr(observation, "update", None)
    if not callable(update):
        return
    try:
        update(**kwargs)
    except Exception:
        return


def _safe_current_update(client: object, **kwargs: Any) -> None:
    for method_name in ("update_current_observation", "update_current_span"):
        method = getattr(client, method_name, None)
        if not callable(method):
            continue
        try:
            method(**kwargs)
            return
        except Exception:
            continue


@dataclass
class ObservationHandle:
    observation: object | None = None

    def record_success(self, *, output: object = None, latency_ms: int | None = None, metadata: dict[str, Any] | None = None) -> None:
        update_metadata = dict(metadata or {})
        update_metadata["status"] = "success"
        if latency_ms is not None:
            update_metadata["latency_ms"] = int(latency_ms)
        _safe_update(
            self.observation,
            output=summarize_for_observability(output),
            metadata=update_metadata,
        )

    def record_failure(self, *, error: BaseException | str, latency_ms: int | None = None) -> None:
        metadata: dict[str, Any] = {
            "status": "failed",
            "error_type": type(error).__name__ if isinstance(error, BaseException) else "Error",
            "error_hash": _hash_text(str(error)),
        }
        if latency_ms is not None:
            metadata["latency_ms"] = int(latency_ms)
        _safe_update(self.observation, metadata=metadata)


@contextmanager
def _start_observation(**kwargs: Any) -> Iterator[ObservationHandle]:
    client = get_langfuse_client()
    if client is None:
        yield ObservationHandle()
        return

    starter = getattr(client, "start_as_current_observation", None)
    if not callable(starter):
        yield ObservationHandle()
        return

    try:
        manager = starter(**kwargs)
        observation = manager.__enter__()
    except Exception:
        yield ObservationHandle()
        return

    exc_info = (None, None, None)
    try:
        yield ObservationHandle(observation=observation)
    except BaseException:
        exc_info = sys.exc_info()
        raise
    finally:
        try:
            manager.__exit__(*exc_info)
        except Exception:
            pass


@contextmanager
def workflow_trace(
    *,
    context: object,
    review_input: object,
    lesson_id: int = 0,
    organization_id: int = 0,
) -> Iterator[ObservationHandle]:
    metadata = {
        "trace_id": getattr(context, "trace_id", ""),
        "lesson_id": int(lesson_id or 0),
        "organization_id": int(organization_id or 0),
        "provider": getattr(context, "provider", ""),
        "model": getattr(context, "model", ""),
        "reasoning_effort": getattr(context, "reasoning_effort", ""),
        "prompt_version": getattr(context, "prompt_version", ""),
        "schema_version": getattr(context, "schema_version", ""),
        "style_version": getattr(context, "style_version", ""),
    }
    with _start_observation(
        as_type="span",
        name="review_plan.workflow",
        trace_context={"trace_id": getattr(context, "trace_id", "")},
        input=summarize_review_input(review_input),
        metadata=metadata,
    ) as handle:
        try:
            yield handle
        except BaseException as exc:
            handle.record_failure(error=exc)
            raise


@contextmanager
def workflow_node_span(*, node_name: str, input_data: object, context: object) -> Iterator[ObservationHandle]:
    with _start_observation(
        as_type="span",
        name=f"review_plan.node.{node_name}",
        input=summarize_for_observability(input_data),
        metadata={
            "trace_id": getattr(context, "trace_id", ""),
            "node_name": node_name,
            "provider": getattr(context, "provider", ""),
            "model": getattr(context, "model", ""),
        },
    ) as handle:
        yield handle


@contextmanager
def llm_generation(
    *,
    provider: str,
    model: str,
    system_prompt: str,
    user_message: str,
    reasoning_effort: str = "",
    stage: str = "generate_json",
    temperature: float | None = None,
) -> Iterator[ObservationHandle]:
    metadata = {
        "provider": provider,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "response_format": "json_object",
        "stage": stage,
    }
    if temperature is not None:
        metadata["temperature"] = float(temperature)
    with _start_observation(
        as_type="generation",
        name="review_plan.llm.generate_json",
        input={
            "system_prompt": _text_summary(system_prompt),
            "user_message": _text_summary(user_message),
        },
        metadata=metadata,
    ) as handle:
        yield handle


def record_quality_score(*, context: object, quality: object) -> None:
    client = get_langfuse_client()
    if client is None:
        return
    payload = quality.model_dump() if hasattr(quality, "model_dump") else quality
    if not isinstance(payload, dict):
        return
    score = max(0, min(100, int(payload.get("score", 0) or 0)))
    passed = bool(payload.get("passed"))
    issue_count = len(payload.get("issues") or [])
    _safe_current_update(
        client,
        metadata={
            "quality_score": score,
            "quality_passed": passed,
            "quality_issue_count": issue_count,
        },
    )
    for method_name in ("create_score", "score_current_trace"):
        method = getattr(client, method_name, None)
        if not callable(method):
            continue
        try:
            if method_name == "create_score":
                method(
                    name="review_plan_quality",
                    value=score,
                    trace_id=getattr(context, "trace_id", ""),
                    comment=f"passed={passed}; issues={issue_count}",
                )
            else:
                method(name="review_plan_quality", value=score, comment=f"passed={passed}; issues={issue_count}")
            break
        except Exception:
            continue


def record_workflow_result(
    *,
    context: object,
    plan: object,
    quality: object,
    usage: object,
    status: str,
) -> None:
    client = get_langfuse_client()
    if client is None:
        return
    quality_payload = quality.model_dump() if hasattr(quality, "model_dump") else quality
    _safe_current_update(
        client,
        output={
            "plan": summarize_review_plan(plan),
            "quality": summarize_for_observability(quality_payload),
            "usage": summarize_usage(usage),
        },
        metadata={
            "status": status,
            "warning_count": len(getattr(context, "warnings", []) or []),
            "node_log_count": len(getattr(context, "logs", []) or []),
        },
    )


def record_workflow_failure(*, context: object, error: BaseException) -> None:
    client = get_langfuse_client()
    if client is None:
        return
    _safe_current_update(
        client,
        metadata={
            "status": "failed",
            "error_type": type(error).__name__,
            "error_hash": _hash_text(str(error)),
            "warning_count": len(getattr(context, "warnings", []) or []),
            "node_log_count": len(getattr(context, "logs", []) or []),
        },
    )


def flush() -> None:
    client = get_langfuse_client()
    if client is None:
        return
    flush_method = getattr(client, "flush", None)
    if callable(flush_method):
        try:
            flush_method()
        except Exception:
            return
