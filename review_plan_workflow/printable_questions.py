from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from review_plan_workflow.schemas import normalize_final_review_plan


@dataclass
class PrintableDayQuestionCounts:
    day: int
    unique_fill_count: int = 0
    unique_choice_count: int = 0
    raw_fill_count: int = 0
    raw_choice_count: int = 0
    answer_item_count: int = 0
    dropped_items: list[str] = field(default_factory=list)

    @property
    def visible_question_count(self) -> int:
        return self.unique_fill_count + self.unique_choice_count


@dataclass
class PrintableQuestionCounts:
    total_visible_questions: int = 0
    total_answer_items: int = 0
    per_day: list[PrintableDayQuestionCounts] = field(default_factory=list)
    dropped_items: list[str] = field(default_factory=list)


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _compact_text(value: str) -> str:
    return re.sub(r"[\s,，。.!！?？、:：;；《》「」“”\"'`（）()\[\]【】\-_/]+", "", value)


def _question_signature(value: object) -> str:
    return _compact_text(_clean_text(value))


def _has_answer(value: dict[str, Any]) -> bool:
    return any(_clean_text(value.get(key)) for key in ("answer", "answer_hint", "reference_answer", "answers"))


def _day_number(value: dict[str, Any]) -> int:
    try:
        return int(value.get("day") or value.get("day_number") or 0)
    except (TypeError, ValueError):
        return 0


def collect_day_printable_question_counts(day: dict[str, Any]) -> PrintableDayQuestionCounts:
    counts = PrintableDayQuestionCounts(day=_day_number(day))
    fill_signatures: set[str] = set()
    choice_signatures: set[str] = set()

    def add_fill(value: object) -> None:
        signature = _question_signature(value)
        if not signature:
            return
        counts.raw_fill_count += 1
        if signature in fill_signatures:
            counts.dropped_items.append(f"duplicate_fill:{signature[:40]}")
            return
        fill_signatures.add(signature)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            item_type = _clean_text(value.get("type")).lower()
            fill_text = value.get("text") or value.get("stem") or value.get("question") or value.get("label")
            if item_type == "fill" or (fill_text and _has_answer(value)):
                add_fill(fill_text)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(day.get("blanks", []))
    walk(day.get("items", []))
    walk(day.get("steps", []))
    walk(day.get("active_recall", {}))
    walk(day.get("tasks", {}))
    walk(day.get("oral_cards", []))

    for choice in day.get("choices", []) if isinstance(day.get("choices"), list) else []:
        if not isinstance(choice, dict):
            continue
        question = choice.get("question") or choice.get("stem")
        signature = _question_signature(question)
        if not signature:
            counts.dropped_items.append("choice_without_question")
            continue
        counts.raw_choice_count += 1
        if signature in choice_signatures:
            counts.dropped_items.append(f"duplicate_choice:{signature[:40]}")
            continue
        choice_signatures.add(signature)

    counts.unique_fill_count = len(fill_signatures)
    counts.unique_choice_count = len(choice_signatures)
    counts.answer_item_count = counts.visible_question_count
    return counts


def _raw_days_by_key(plan: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    days = plan.get("days") if isinstance(plan.get("days"), list) else []
    keyed: dict[int, dict[str, Any]] = {}
    indexed: list[dict[str, Any]] = []
    for day in days:
        if not isinstance(day, dict):
            continue
        indexed.append(day)
        day_key = _day_number(day)
        if day_key and day_key not in keyed:
            keyed[day_key] = day
    return keyed, indexed


def _matching_raw_day(
    normalized_day: dict[str, Any],
    index: int,
    keyed_raw_days: dict[int, dict[str, Any]],
    indexed_raw_days: list[dict[str, Any]],
) -> dict[str, Any] | None:
    day_key = _day_number(normalized_day)
    if day_key and day_key in keyed_raw_days:
        return keyed_raw_days[day_key]
    if index < len(indexed_raw_days):
        return indexed_raw_days[index]
    return None


def merge_visible_and_raw_counts(
    visible_counts: PrintableDayQuestionCounts,
    raw_counts: PrintableDayQuestionCounts | None,
) -> PrintableDayQuestionCounts:
    if raw_counts is None:
        return visible_counts
    return PrintableDayQuestionCounts(
        day=visible_counts.day,
        unique_fill_count=visible_counts.unique_fill_count,
        unique_choice_count=visible_counts.unique_choice_count,
        raw_fill_count=raw_counts.raw_fill_count,
        raw_choice_count=raw_counts.raw_choice_count,
        answer_item_count=visible_counts.answer_item_count,
        dropped_items=raw_counts.dropped_items,
    )


def count_printable_questions(plan: dict[str, Any], *, raw_plan: dict[str, Any] | None = None) -> PrintableQuestionCounts:
    normalized = normalize_final_review_plan(plan)
    days = normalized.get("days") if isinstance(normalized.get("days"), list) else []
    keyed_raw_days, indexed_raw_days = _raw_days_by_key(raw_plan if raw_plan is not None else plan)
    result = PrintableQuestionCounts()
    for index, day in enumerate(days):
        if not isinstance(day, dict):
            result.dropped_items.append("non_dict_day")
            continue
        visible_counts = collect_day_printable_question_counts(day)
        raw_day = _matching_raw_day(day, index, keyed_raw_days, indexed_raw_days)
        raw_counts = collect_day_printable_question_counts(raw_day) if isinstance(raw_day, dict) else None
        day_counts = merge_visible_and_raw_counts(visible_counts, raw_counts)
        result.per_day.append(day_counts)
        result.total_visible_questions += day_counts.visible_question_count
        result.total_answer_items += day_counts.answer_item_count
        result.dropped_items.extend(day_counts.dropped_items)
    return result
