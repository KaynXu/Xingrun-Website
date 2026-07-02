from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template
from review_plan_workflow.printable_questions import count_printable_questions
from review_plan_workflow.schemas import LessonSourcePack, normalize_final_review_plan, validate_final_review_plan


class ReviewPlanValidationIssue(BaseModel):
    model_config = ConfigDict(extra="allow")

    severity: Literal["low", "medium", "high"] = "medium"
    category: str
    description: str
    target_path: str = ""


class ReviewPlanValidationResult(BaseModel):
    passed: bool
    issues: list[ReviewPlanValidationIssue] = Field(default_factory=list)
    printable_question_count: int = 0
    rendered_question_count: int = 0


def _clean_text(value: object) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value or "").strip()


def _iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_iter_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_iter_strings(item))
        return strings
    return []


def _math_placeholder_ids(plan: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for text in _iter_strings(plan):
        ids.update(match.group(1).strip() for match in re.finditer(r"\{\{math:([^}]+)\}\}", text))
    return {item for item in ids if item}


def _math_block_ids(plan: dict[str, Any]) -> set[str]:
    knowledge_sections = plan.get("knowledge_sections") if isinstance(plan.get("knowledge_sections"), dict) else {}
    blocks = knowledge_sections.get("math_blocks") if isinstance(knowledge_sections.get("math_blocks"), list) else []
    return {_clean_text(block.get("id")) for block in blocks if isinstance(block, dict) and _clean_text(block.get("id"))}


def _source_coverage_ids(plan: dict[str, Any]) -> set[str]:
    knowledge_sections = plan.get("knowledge_sections") if isinstance(plan.get("knowledge_sections"), dict) else {}
    coverage = knowledge_sections.get("source_coverage") if isinstance(knowledge_sections.get("source_coverage"), list) else []
    return {
        _clean_text(item.get("source_segment_id"))
        for item in coverage
        if isinstance(item, dict) and _clean_text(item.get("source_segment_id"))
    }


def _source_pack_segment_ids(source_pack: LessonSourcePack | dict[str, Any] | None) -> set[str]:
    if source_pack is None:
        return set()
    if isinstance(source_pack, dict):
        parsed = LessonSourcePack.model_validate(source_pack)
    else:
        parsed = source_pack
    return {segment.id for segment in parsed.segments if segment.id}


def _rendered_question_count(plan: dict[str, Any]) -> int:
    _lesson, days, _reminders = adapt_plan_to_review_template(plan)
    total = 0
    for day in days:
        if not isinstance(day, dict):
            continue
        blanks = day.get("blanks") if isinstance(day.get("blanks"), list) else []
        choices = day.get("choices") if isinstance(day.get("choices"), list) else []
        total += len(blanks) + len(choices)
    return total


def validate_review_plan_delivery(
    plan: dict[str, Any],
    *,
    required_review_days: list[int] | None = None,
    constraints: dict[str, Any] | None = None,
    source_pack: LessonSourcePack | dict[str, Any] | None = None,
) -> ReviewPlanValidationResult:
    issues: list[ReviewPlanValidationIssue] = []
    normalized = normalize_final_review_plan(plan)
    final_plan, schema_errors = validate_final_review_plan(normalized)
    if schema_errors:
        issues.append(
            ReviewPlanValidationIssue(
                severity="high",
                category="schema",
                description="复习计划结构不完整：" + "；".join(schema_errors[:3]),
            )
        )

    days = normalized.get("days") if isinstance(normalized.get("days"), list) else []
    if required_review_days is not None:
        day_numbers = {int(day.get("day") or 0) for day in days if isinstance(day, dict)}
        if day_numbers != set(required_review_days):
            issues.append(
                ReviewPlanValidationIssue(
                    severity="high",
                    category="schedule",
                    description=f"复习日必须且只能是 {required_review_days}，当前是 {sorted(day_numbers)}。",
                    target_path="days",
                )
            )

    printable_counts = count_printable_questions(normalized)
    requested_count = None
    if isinstance(constraints, dict) and isinstance(constraints.get("requested_question_count"), int):
        requested_count = int(constraints["requested_question_count"])
    if requested_count is not None and printable_counts.total_visible_questions != requested_count:
        issues.append(
            ReviewPlanValidationIssue(
                severity="high",
                category="constraints",
                description=f"老师要求 {requested_count} 道可打印题，当前是 {printable_counts.total_visible_questions} 道。",
            )
        )

    for day_index, day in enumerate(days):
        if not isinstance(day, dict):
            continue
        blanks = day.get("blanks") if isinstance(day.get("blanks"), list) else []
        choices = day.get("choices") if isinstance(day.get("choices"), list) else []
        for blank_index, blank in enumerate(blanks):
            if isinstance(blank, dict) and not _clean_text(blank.get("answer")):
                issues.append(
                    ReviewPlanValidationIssue(
                        severity="high",
                        category="answers",
                        description="填空题缺少答案。",
                        target_path=f"days[{day_index}].blanks[{blank_index}]",
                    )
                )
        for choice_index, choice in enumerate(choices):
            if isinstance(choice, dict) and not _clean_text(choice.get("answer")):
                issues.append(
                    ReviewPlanValidationIssue(
                        severity="high",
                        category="answers",
                        description="选择题缺少答案。",
                        target_path=f"days[{day_index}].choices[{choice_index}]",
                    )
                )
        body_items = day.get("items") if isinstance(day.get("items"), list) else []
        has_action = any(isinstance(item, dict) and _clean_text(item.get("text")) for item in body_items)
        has_output = bool(_clean_text(day.get("completion_standard"))) or any(
            isinstance(item, dict) and _clean_text(item.get("text")).startswith("产出：") for item in body_items
        )
        if final_plan is not None and not has_action:
            issues.append(
                ReviewPlanValidationIssue(
                    severity="medium",
                    category="task_actionability",
                    description="复习日缺少可执行动作。",
                    target_path=f"days[{day_index}].items",
                )
            )
        if final_plan is not None and not has_output:
            issues.append(
                ReviewPlanValidationIssue(
                    severity="medium",
                    category="task_actionability",
                    description="复习日缺少完成产出。",
                    target_path=f"days[{day_index}].completion_standard",
                )
            )

    missing_math_blocks = _math_placeholder_ids(normalized) - _math_block_ids(normalized)
    for math_id in sorted(missing_math_blocks):
        issues.append(
            ReviewPlanValidationIssue(
                severity="high",
                category="math_blocks",
                description=f"公式占位符缺少对应 math block：{math_id}",
            )
        )

    segment_ids = _source_pack_segment_ids(source_pack)
    if segment_ids:
        missing_segments = _source_coverage_ids(normalized) - segment_ids
        for segment_id in sorted(missing_segments):
            issues.append(
                ReviewPlanValidationIssue(
                    severity="high",
                    category="source_coverage",
                    description=f"source_coverage 引用了不存在的 segment：{segment_id}",
                )
            )

    rendered_count = 0
    if not schema_errors:
        try:
            rendered_count = _rendered_question_count(normalized)
        except Exception as exc:
            issues.append(
                ReviewPlanValidationIssue(
                    severity="high",
                    category="renderer",
                    description="PDF 渲染 dry run 失败：" + str(exc),
                )
            )
        if rendered_count != printable_counts.total_visible_questions:
            issues.append(
                ReviewPlanValidationIssue(
                    severity="high",
                    category="renderer",
                    description=(
                        f"PDF dry run 可见题量 {rendered_count} 与 canonical 可打印题量 "
                        f"{printable_counts.total_visible_questions} 不一致。"
                    ),
                )
            )

    return ReviewPlanValidationResult(
        passed=not any(issue.severity == "high" for issue in issues),
        issues=issues,
        printable_question_count=printable_counts.total_visible_questions,
        rendered_question_count=rendered_count,
    )
