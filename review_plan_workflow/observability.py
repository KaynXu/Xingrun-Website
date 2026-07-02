from __future__ import annotations

import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from config_runtime import get_runtime_config
from review_plan_workflow.generation_options import generation_options_trace_summary, normalize_generation_options


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


def _count_source_brief_field(data: dict[str, Any], list_key: str, count_key: str) -> int:
    if count_key in data:
        return max(0, int(data.get(count_key) or 0))
    value = data.get(list_key)
    return len(value) if isinstance(value, list) else 0


def _looks_like_source_brief(data: dict[str, Any]) -> bool:
    if "source_text_hash" not in data or "confidence" not in data:
        return False
    return any(
        key in data
        for key in (
            "cleaned_text",
            "cleaned_text_length",
            "lesson_title_candidates",
            "lesson_title_candidates_count",
            "knowledge_points",
            "knowledge_points_count",
            "evidence_map",
            "evidence_count",
        )
    )


def summarize_source_brief(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        try:
            data = value.model_dump()
        except Exception:
            data = {}
    elif isinstance(value, dict):
        data = value
    else:
        data = {}
    return {
        "schema_version": str(data.get("schema_version") or ""),
        "source_text_hash": str(data.get("source_text_hash") or ""),
        "lesson_title_candidates_count": _count_source_brief_field(
            data,
            "lesson_title_candidates",
            "lesson_title_candidates_count",
        ),
        "knowledge_points_count": _count_source_brief_field(data, "knowledge_points", "knowledge_points_count"),
        "method_chains_count": _count_source_brief_field(data, "method_chains", "method_chains_count"),
        "common_mistakes_count": _count_source_brief_field(data, "common_mistakes", "common_mistakes_count"),
        "example_stems_count": _count_source_brief_field(data, "example_stems", "example_stems_count"),
        "teacher_emphasis_count": _count_source_brief_field(data, "teacher_emphasis", "teacher_emphasis_count"),
        "excluded_noise_count": _count_source_brief_field(data, "excluded_noise", "excluded_noise_count"),
        "missing_fields": list(data.get("missing_fields") or [])[:10],
        "evidence_count": _count_source_brief_field(data, "evidence_map", "evidence_count"),
        "confidence": float(data.get("confidence") or 0.0),
    }


def summarize_evidence_map(value: object) -> dict[str, Any]:
    if isinstance(value, list):
        return {"type": "list", "count": len(value)}
    return {"type": type(value).__name__, "count": 0}


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
        if _looks_like_source_brief(value):
            return summarize_source_brief(value)

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
            if _safe_key(key_text) == "source_brief":
                fields[key_text] = summarize_source_brief(item)
            elif _safe_key(key_text) == "evidence_map":
                fields[key_text] = summarize_evidence_map(item)
            elif isinstance(item, str):
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
        "generation_options": generation_options_trace_summary(
            normalize_generation_options(
                {
                    "schedule_mode": data.get("schedule_mode") or "standard",
                    "review_days": data.get("review_days") or [1, 2, 7, 14, 30],
                    "daily_count": data.get("daily_count"),
                    "user_requirements": data.get("user_requirements") or "",
                }
            )
        ),
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


def _count_model_config_call(node_outputs: dict[str, Any], key: str) -> int:
    value = node_outputs.get(key)
    if not isinstance(value, dict):
        return 0
    return 1 if isinstance(value.get("usage"), dict) else 0


def _count_attempts(node_outputs: dict[str, Any], key: str) -> int:
    value = node_outputs.get(key)
    if not isinstance(value, list):
        return 0
    return len([item for item in value if isinstance(item, dict)])


def _count_success_logs(logs: list[object], node_name: str) -> int:
    return len(
        [
            log
            for log in logs
            if str(getattr(log, "node_name", "") or "") == node_name
            and str(getattr(log, "status", "") or "") == "success"
        ]
    )


def _count_by_key(items: object, key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(items, list):
        return counts
    for item in items:
        if not isinstance(item, dict):
            continue
        value = str(item.get(key) or "").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return counts


def _issue_summary(items: object) -> dict[str, Any]:
    issues = items if isinstance(items, list) else []
    return {
        "count": len(issues),
        "by_severity": _count_by_key(issues, "severity"),
        "by_category": _count_by_key(issues, "category"),
    }


def _compact_result_summary(payload: object) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    return {
        "passed": bool(data.get("passed")),
        "must_revise": bool(data.get("must_revise")),
        "score": int(data.get("score") or 0),
        "issues": _issue_summary(data.get("issues")),
    }


def _review_input_contract_summary(review_input: object | None) -> dict[str, Any]:
    if review_input is None:
        return {}
    if hasattr(review_input, "model_dump"):
        try:
            data = review_input.model_dump()
        except Exception:
            data = {}
    elif isinstance(review_input, dict):
        data = review_input
    else:
        data = {}
    source_pack = data.get("source_pack") if isinstance(data.get("source_pack"), dict) else {}
    constraints = data.get("constraints") if isinstance(data.get("constraints"), dict) else {}
    return {
        "source_hash": str(
            source_pack.get("raw_source_hash")
            or source_pack.get("source_hash")
            or data.get("source_text_hash")
            or ""
        ),
        "source_type": str(source_pack.get("source_type") or "text"),
        "generation_mode": str(data.get("schedule_mode") or ""),
        "review_days": list(data.get("review_days") or []),
        "parsed_teacher_constraints": {
            key: value
            for key, value in constraints.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        },
    }


def build_delivery_contract_summary(context: object, *, review_input: object | None = None) -> dict[str, Any]:
    node_outputs = getattr(context, "node_outputs", {}) or {}
    if not isinstance(node_outputs, dict):
        node_outputs = {}
    validator = node_outputs.get("review_plan_validator") if isinstance(node_outputs.get("review_plan_validator"), dict) else {}
    evaluator = node_outputs.get("review_plan_evaluator") if isinstance(node_outputs.get("review_plan_evaluator"), dict) else {}
    renderer_report = validator.get("renderer_report") if isinstance(validator.get("renderer_report"), dict) else {}
    source_brief = node_outputs.get("source_brief") if isinstance(node_outputs.get("source_brief"), dict) else {}
    input_summary = _review_input_contract_summary(review_input)
    if not input_summary.get("source_hash"):
        input_summary["source_hash"] = str(source_brief.get("source_text_hash") or "")
    return {
        **input_summary,
        "source_pack_confidence": float(source_brief.get("confidence") or 0.0),
        "validator_result": {
            **_compact_result_summary(validator),
            "printable_question_count": int(validator.get("printable_question_count") or 0),
            "rendered_question_count": int(validator.get("rendered_question_count") or 0),
            "answer_key_count": int(validator.get("answer_key_count") or 0),
        },
        "evaluator_result": {
            **_compact_result_summary(evaluator),
            "validator_passed": bool(evaluator.get("validator_passed", True)),
            "llm_review_used": bool(evaluator.get("llm_review_used")),
        },
        "visible_question_count": int(renderer_report.get("visible_question_count") or validator.get("rendered_question_count") or 0),
        "answer_key_count": int(renderer_report.get("answer_key_count") or validator.get("answer_key_count") or 0),
        "renderer_dropped_count": len(renderer_report.get("dropped_items") or []),
        "renderer_formula_failure_count": len(renderer_report.get("formula_failures") or []),
    }


def build_workflow_runtime_summary(
    context: object,
    *,
    usage: object | None = None,
    review_input: object | None = None,
) -> dict[str, Any]:
    node_outputs = getattr(context, "node_outputs", {}) or {}
    if not isinstance(node_outputs, dict):
        node_outputs = {}
    logs = getattr(context, "logs", []) or []
    latency_by_stage: dict[str, int] = {}
    failed_stages: list[str] = []
    for log in logs:
        node_name = str(getattr(log, "node_name", "") or "")
        if not node_name:
            continue
        latency_by_stage[node_name] = latency_by_stage.get(node_name, 0) + max(0, int(getattr(log, "latency_ms", 0) or 0))
        if str(getattr(log, "status", "") or "") == "failed":
            failed_stages.append(node_name)

    question_repair_count = _count_attempts(node_outputs, "question_repair_attempts")
    if question_repair_count == 0:
        question_repair_count = _count_success_logs(logs, "question_repair")
    revision_count = _count_attempts(node_outputs, "revision_attempts")
    if revision_count == 0:
        revision_count = _count_success_logs(logs, "revision")
    plan_generator_calls = _count_attempts(node_outputs, "plan_generator_attempts")
    if plan_generator_calls == 0 and _count_model_config_call(node_outputs, "plan_generator_model_config"):
        plan_generator_calls = 1
    llm_reviewer_calls = _count_success_logs(logs, "quality_reviewer_llm")
    if llm_reviewer_calls == 0:
        llm_reviewer_calls = _count_model_config_call(node_outputs, "quality_reviewer_llm_model_config")
    parent_planner_calls = _count_success_logs(logs, "parent_planner")
    if parent_planner_calls == 0:
        parent_planner_calls = _count_model_config_call(node_outputs, "parent_planner_model_config")
    model_call_count = (
        parent_planner_calls
        + plan_generator_calls
        + llm_reviewer_calls
        + question_repair_count
        + revision_count
    )
    repair_count = question_repair_count + revision_count
    path = "high_quality_path" if llm_reviewer_calls or repair_count else "fast_path"
    return {
        "path": path,
        "model_call_count": model_call_count,
        "parent_planner_model_call_count": parent_planner_calls,
        "writer_model_call_count": plan_generator_calls,
        "llm_reviewer_model_call_count": llm_reviewer_calls,
        "repair_model_call_count": repair_count,
        "question_repair_count": question_repair_count,
        "revision_count": revision_count,
        "latency_by_stage": latency_by_stage,
        "total_node_latency_ms": sum(latency_by_stage.values()),
        "failed_stages": failed_stages,
        "usage": summarize_usage(usage or {}),
        "delivery_contract": build_delivery_contract_summary(context, review_input=review_input),
    }


def review_plan_langfuse_enabled() -> bool:
    cfg = get_runtime_config()
    if not bool(cfg.get("review_plan_langfuse_enabled")):
        return False
    return bool(cfg.get("langfuse_public_key") and cfg.get("langfuse_secret_key"))


def _ensure_langfuse_env() -> None:
    cfg = get_runtime_config()
    public_key = str(cfg.get("langfuse_public_key") or os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = str(cfg.get("langfuse_secret_key") or os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()
    base_url = str(
        cfg.get("langfuse_base_url")
        or os.environ.get("LANGFUSE_BASE_URL")
        or os.environ.get("LANGFUSE_HOST")
        or ""
    ).strip()
    if public_key:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", public_key)
    if secret_key:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", secret_key)
    if base_url:
        os.environ.setdefault("LANGFUSE_BASE_URL", base_url)
        os.environ.setdefault("LANGFUSE_HOST", base_url)


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
    node_outputs = getattr(context, "node_outputs", {}) or {}
    runtime = node_outputs.get("workflow_runtime") if isinstance(node_outputs, dict) else None
    if not isinstance(runtime, dict):
        runtime = build_workflow_runtime_summary(context, usage=usage)
    _safe_current_update(
        client,
        output={
            "plan": summarize_review_plan(plan),
            "quality": summarize_for_observability(quality_payload),
            "usage": summarize_usage(usage),
            "runtime": runtime,
        },
        metadata={
            "status": status,
            "warning_count": len(getattr(context, "warnings", []) or []),
            "node_log_count": len(getattr(context, "logs", []) or []),
            "model_call_count": runtime["model_call_count"],
            "workflow_path": runtime["path"],
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
