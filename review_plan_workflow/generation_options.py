from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


STANDARD_REVIEW_DAYS = [1, 2, 7, 14, 30]
SUPPORTED_SCHEDULE_MODES = {"standard", "compressed", "daily", "custom"}
MAX_REVIEW_DAYS = 30
MAX_USER_REQUIREMENTS_CHARS = 1000
QUESTION_COUNT_PATTERNS = (
    re.compile(r"(?:题目|题量|练习|可打印题|打印题)?\s*(?:控制|限制|限定|保持|总共|一共|共|只要|不要超过|不超过|至少)?\s*在?\s*(\d{1,2})\s*(?:道)?\s*题"),
    re.compile(r"(\d{1,2})\s*(?:道)?\s*(?:题目|题量|练习|可打印题|打印题)"),
)


def _coerce_mapping(value: object | None) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("generation_options must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("generation_options must be an object")
        return dict(parsed)
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError("generation_options must be an object")


def _coerce_positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    if value > MAX_REVIEW_DAYS:
        raise ValueError(f"{field_name} must be at most {MAX_REVIEW_DAYS}")
    return value


def _parse_review_days(value: object) -> list[int]:
    if isinstance(value, str):
        raw_items: Sequence[object] = [item.strip() for item in value.split(",")]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        raw_items = value
    else:
        raise ValueError("review_days must be a list or comma string")

    days: list[int] = []
    for item in raw_items:
        if item == "":
            continue
        if isinstance(item, str):
            if not item.isdigit():
                raise ValueError("review_days must contain positive integers")
            day = int(item)
        else:
            day = _coerce_positive_int(item, field_name="review_days")
        days.append(_coerce_positive_int(day, field_name="review_days"))
    days = sorted(set(days))
    if not days:
        raise ValueError("review_days must not be empty")
    if len(days) > MAX_REVIEW_DAYS:
        raise ValueError(f"review_days can contain at most {MAX_REVIEW_DAYS} days")
    return days


def _clean_user_requirements(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > MAX_USER_REQUIREMENTS_CHARS:
        return text[:MAX_USER_REQUIREMENTS_CHARS]
    return text


def _parse_requested_question_count(requirements: str) -> int | None:
    text = str(requirements or "").strip()
    if not text:
        return None
    for pattern in QUESTION_COUNT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        count = int(match.group(1))
        if 1 <= count <= 30:
            return count
    return None


def parse_generation_constraints(user_requirements: object) -> dict[str, object]:
    requirements = _clean_user_requirements(user_requirements)
    requested_question_count = _parse_requested_question_count(requirements)
    return {
        "requested_question_count": requested_question_count,
    }


def _merge_raw_constraints(parsed: dict[str, object], raw_constraints: object) -> dict[str, object]:
    constraints = dict(parsed)
    if not isinstance(raw_constraints, Mapping):
        return constraints
    if isinstance(raw_constraints.get("force_parent_planner"), bool):
        constraints["force_parent_planner"] = raw_constraints["force_parent_planner"]
    return constraints


def normalize_generation_options(value: object | None, *, source: str = "create") -> dict[str, object]:
    raw = _coerce_mapping(value)
    mode = str(raw.get("schedule_mode") or "standard").strip() or "standard"
    if mode not in SUPPORTED_SCHEDULE_MODES:
        raise ValueError("schedule_mode must be standard, compressed, daily, or custom")

    daily_count: int | None = None
    if mode == "standard":
        review_days = list(STANDARD_REVIEW_DAYS)
    elif mode == "compressed":
        review_days = [1]
        daily_count = 1
    elif mode == "daily":
        daily_count = _coerce_positive_int(raw.get("daily_count"), field_name="daily_count")
        review_days = list(range(1, daily_count + 1))
    else:
        review_days = _parse_review_days(raw.get("review_days"))

    user_requirements = _clean_user_requirements(raw.get("user_requirements"))
    constraints = _merge_raw_constraints(
        parse_generation_constraints(user_requirements),
        raw.get("constraints"),
    )
    return {
        "schedule_mode": mode,
        "review_days": review_days,
        "daily_count": daily_count,
        "user_requirements": user_requirements,
        "constraints": constraints,
        "source": str(source or raw.get("source") or "create").strip() or "create",
    }


def generation_options_summary(options: Mapping[str, object]) -> str:
    mode = str(options.get("schedule_mode") or "standard")
    review_days = options.get("review_days") if isinstance(options.get("review_days"), list) else []
    if mode == "compressed":
        return "当天课后复习"
    if mode == "daily":
        daily_count = options.get("daily_count") or len(review_days)
        return f"每日连续 {daily_count} 天"
    if mode == "custom":
        return "自定义日期 " + ",".join(str(day) for day in review_days)
    return f"{len(review_days) or len(STANDARD_REVIEW_DAYS)}次间隔复习"


def generation_options_trace_summary(options: Mapping[str, object]) -> dict[str, object]:
    requirements = str(options.get("user_requirements") or "").strip()
    summary: dict[str, object] = {
        "schedule_mode": str(options.get("schedule_mode") or "standard"),
        "review_days": list(options.get("review_days") or STANDARD_REVIEW_DAYS),
        "daily_count": options.get("daily_count"),
        "has_user_requirements": bool(requirements),
        "source": str(options.get("source") or "create"),
    }
    if requirements:
        summary["user_requirements_preview"] = requirements[:40]
    constraints = options.get("constraints")
    if isinstance(constraints, Mapping):
        requested_question_count = constraints.get("requested_question_count")
        if isinstance(requested_question_count, int):
            summary["requested_question_count"] = requested_question_count
    return summary
