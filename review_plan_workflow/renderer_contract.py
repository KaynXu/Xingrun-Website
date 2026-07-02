from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template
from review_plan_workflow.printable_questions import count_printable_questions
from review_plan_workflow.schemas import normalize_final_review_plan


class RendererDayReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    day: int = 0
    visible_question_count: int = 0
    answer_key_count: int = 0
    blank_count: int = 0
    choice_count: int = 0
    dropped_items: list[str] = Field(default_factory=list)


class RendererDryRunReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    passed: bool = True
    visible_question_count: int = 0
    answer_key_count: int = 0
    canonical_visible_question_count: int = 0
    canonical_answer_key_count: int = 0
    dropped_items: list[str] = Field(default_factory=list)
    formula_failures: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    per_day: list[RendererDayReport] = Field(default_factory=list)


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _day_number(value: object) -> int:
    if isinstance(value, dict):
        value = value.get("offset") or value.get("day")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _blank_has_answer(blank: object) -> bool:
    if isinstance(blank, dict):
        return bool(_clean_text(blank.get("answer")))
    if isinstance(blank, (list, tuple)) and len(blank) > 1:
        return bool(_clean_text(blank[1]))
    return False


def _choice_has_answer(choice: object) -> bool:
    return isinstance(choice, dict) and bool(_clean_text(choice.get("answer")))


def _is_renderer_fallback_blank(blank: object) -> bool:
    text = ""
    answer = ""
    if isinstance(blank, dict):
        text = _clean_text(blank.get("text"))
        answer = _clean_text(blank.get("answer"))
    elif isinstance(blank, (list, tuple)) and blank:
        text = _clean_text(blank[0])
        answer = _clean_text(blank[1] if len(blank) > 1 else "")
    return "关键空格" in text and answer == "见课堂笔记"


def _iter_visible_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested in value.values():
            strings.extend(_iter_visible_strings(nested))
        return strings
    if isinstance(value, (list, tuple)):
        strings = []
        for nested in value:
            strings.extend(_iter_visible_strings(nested))
        return strings
    return []


def _formula_failures_from_rendered_days(days: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for day_index, day in enumerate(days):
        if not isinstance(day, dict):
            continue
        visible_payload = {
            "day": day.get("day"),
            "focus": day.get("focus"),
            "goal": day.get("goal"),
            "tasks": day.get("tasks"),
            "blanks": day.get("blanks"),
            "choices": day.get("choices"),
            "method_cards": day.get("method_cards"),
            "quotes": day.get("quotes"),
        }
        visible_strings = _iter_visible_strings(visible_payload)
        visible_blob = "\n".join(visible_strings)
        for token in sorted(set(re.findall(r"\{\{math:[^}]+\}\}", visible_blob))):
            failures.append(f"day[{day_index}]:unresolved_placeholder:{token}")
        if re.search(r"\{['\"](?:intro|steps|answers|cards)['\"]\s*:", visible_blob):
            failures.append(f"day[{day_index}]:dict_literal_rendered")
    return failures


def dry_run_review_plan_renderer(plan: dict[str, Any]) -> RendererDryRunReport:
    normalized = normalize_final_review_plan(plan)
    canonical = count_printable_questions(normalized, raw_plan=plan)
    report = RendererDryRunReport(
        canonical_visible_question_count=canonical.total_visible_questions,
        canonical_answer_key_count=canonical.total_answer_items,
        dropped_items=list(canonical.dropped_items),
    )
    try:
        _lesson, days, _reminders = adapt_plan_to_review_template(normalized)
    except Exception as exc:
        report.errors.append(str(exc))
        report.passed = False
        return report

    for index, day in enumerate(days):
        if not isinstance(day, dict):
            report.dropped_items.append(f"renderer_non_dict_day:{index}")
            continue
        blanks = day.get("blanks") if isinstance(day.get("blanks"), list) else []
        choices = day.get("choices") if isinstance(day.get("choices"), list) else []
        dropped_items: list[str] = []
        for blank_index, blank in enumerate(blanks):
            if _is_renderer_fallback_blank(blank) and canonical.total_visible_questions == 0:
                dropped_items.append(f"renderer_fallback_blank:{blank_index}")
            if not _blank_has_answer(blank):
                dropped_items.append(f"rendered_blank_without_answer:{blank_index}")
        for choice_index, choice in enumerate(choices):
            if not _choice_has_answer(choice):
                dropped_items.append(f"rendered_choice_without_answer:{choice_index}")
        day_report = RendererDayReport(
            day=_day_number(day),
            blank_count=len(blanks),
            choice_count=len(choices),
            visible_question_count=len(blanks) + len(choices),
            answer_key_count=sum(1 for blank in blanks if _blank_has_answer(blank))
            + sum(1 for choice in choices if _choice_has_answer(choice)),
            dropped_items=dropped_items,
        )
        report.per_day.append(day_report)
        report.visible_question_count += day_report.visible_question_count
        report.answer_key_count += day_report.answer_key_count
        report.dropped_items.extend(dropped_items)

    report.formula_failures.extend(_formula_failures_from_rendered_days(days))
    if report.visible_question_count != report.canonical_visible_question_count:
        report.dropped_items.append(
            f"renderer_visible_count_mismatch:{report.visible_question_count}!={report.canonical_visible_question_count}"
        )
    if report.answer_key_count != report.visible_question_count:
        report.dropped_items.append(f"renderer_answer_count_mismatch:{report.answer_key_count}!={report.visible_question_count}")
    report.passed = not (report.errors or report.formula_failures or report.dropped_items)
    return report
