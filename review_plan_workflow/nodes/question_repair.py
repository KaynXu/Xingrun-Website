from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from config_runtime import (
    resolve_review_plan_repair_temperature,
    resolve_review_plan_writer_model,
    resolve_review_plan_writer_provider,
)
from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm.client import generate_review_plan_json
from review_plan_workflow.llm.prompt_renderer import render_prompt
from review_plan_workflow.schemas import (
    AgenticPlanBlueprint,
    PromptBundle,
    QualityIssue,
    QualityReview,
    ReviewPlanInput,
    ReviewPlanSourceBrief,
    normalize_final_review_plan,
)
from review_plan_workflow.source_brief import source_brief_trace_payload
from review_plan_workflow.state import WorkflowContext


REPAIRABLE_QUESTION_CATEGORIES = {"question_quality", "factuality", "pdf_safety"}


@dataclass(frozen=True)
class QuestionRepairTarget:
    target_id: str
    day: int
    day_position: int
    kind: str
    question_position: int
    issue: QualityIssue
    question: dict[str, Any]
    day_context: dict[str, Any]


_CN_TARGET_PATTERNS = [
    re.compile(r"第\s*(?P<day>\d+)\s*天.*?(?P<kind>选择题|选择|choice|choices|填空题|填空|blank|blanks).*?第\s*(?P<index>\d+)\s*题", re.I),
    re.compile(r"第\s*(?P<day>\d+)\s*天.*?第\s*(?P<index>\d+)\s*题.*?(?P<kind>选择题|选择|choice|choices|填空题|填空|blank|blanks)", re.I),
]
_PATH_TARGET_RE = re.compile(r"days\[(?P<day_index>\d+)\]\.(?P<kind>choices|blanks)\[(?P<question_index>\d+)\]", re.I)


def _kind_from_text(value: str) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ("选择", "choice")):
        return "choice"
    if any(token in text for token in ("填空", "blank")):
        return "blank"
    return ""


def _issue_location(issue: QualityIssue) -> tuple[int | None, str, int | None]:
    day_value = getattr(issue, "day", None) or getattr(issue, "day_index", None)
    question_value = getattr(issue, "question_index", None)
    kind_value = _kind_from_text(getattr(issue, "question_type", ""))
    if day_value and question_value and kind_value:
        try:
            return int(day_value), kind_value, int(question_value)
        except (TypeError, ValueError):
            pass

    haystack = " ".join(
        text
        for text in (issue.description, issue.suggested_fix, *[])
        if isinstance(text, str)
    )
    for pattern in _CN_TARGET_PATTERNS:
        match = pattern.search(haystack)
        if match:
            return int(match.group("day")), _kind_from_text(match.group("kind")), int(match.group("index"))
    return None, "", None


def _day_context(day: dict[str, Any]) -> dict[str, Any]:
    return {
        "day": day.get("day"),
        "label": day.get("label", ""),
        "title": day.get("title", ""),
        "goal": day.get("goal", ""),
        "focus": day.get("focus", ""),
        "theme": day.get("theme", ""),
        "completion_standard": day.get("completion_standard", ""),
    }


def find_question_repair_targets(plan: dict[str, Any], quality: QualityReview) -> list[QuestionRepairTarget]:
    high_issues = [issue for issue in quality.issues if issue.severity == "high"]
    if any(issue.category not in REPAIRABLE_QUESTION_CATEGORIES for issue in high_issues):
        return []
    repairable_issues = [
        issue
        for issue in quality.issues
        if issue.severity == "high" and issue.category in REPAIRABLE_QUESTION_CATEGORIES
    ]
    if not repairable_issues:
        return []

    normalized = normalize_final_review_plan(plan)
    days = normalized.get("days") if isinstance(normalized.get("days"), list) else []
    targets: list[QuestionRepairTarget] = []
    seen: set[str] = set()
    for issue in repairable_issues:
        path_match = _PATH_TARGET_RE.search(str(getattr(issue, "target_path", "") or ""))
        if path_match:
            day_position = int(path_match.group("day_index"))
            kind = "choice" if path_match.group("kind").lower() == "choices" else "blank"
            question_number = int(path_match.group("question_index")) + 1
        else:
            day_number, kind, question_number = _issue_location(issue)
            if not day_number or not kind or not question_number:
                return []
            day_position = next(
                (index for index, day in enumerate(days) if isinstance(day, dict) and int(day.get("day") or 0) == day_number),
                -1,
            )
        if day_position < 0:
            return []
        if day_position >= len(days) or not isinstance(days[day_position], dict):
            return []
        day = days[day_position]
        day_number = int(day.get("day") or 0)
        if not day_number:
            return []
        collection_name = "choices" if kind == "choice" else "blanks"
        collection = day.get(collection_name) if isinstance(day.get(collection_name), list) else []
        if question_number < 1 or question_number > len(collection) or not isinstance(collection[question_number - 1], dict):
            return []
        target_id = f"day{day_number}_{kind}{question_number}"
        if target_id in seen:
            continue
        seen.add(target_id)
        targets.append(
            QuestionRepairTarget(
                target_id=target_id,
                day=day_number,
                day_position=day_position,
                kind=kind,
                question_position=question_number - 1,
                issue=issue,
                question=copy.deepcopy(collection[question_number - 1]),
                day_context=_day_context(day),
            )
        )
    return targets


def can_repair_questions(plan: dict[str, Any], quality: QualityReview) -> bool:
    return bool(find_question_repair_targets(plan, quality))


def _compact_source_brief(prompt_bundle: PromptBundle, source_brief: ReviewPlanSourceBrief | None) -> dict[str, Any]:
    safe_brief = prompt_bundle.variables.get("source_brief")
    if not isinstance(safe_brief, dict) and source_brief is not None:
        safe_brief = source_brief_trace_payload(source_brief)
    if not isinstance(safe_brief, dict):
        return {}
    return {
        key: safe_brief.get(key)
        for key in ("lesson_title_candidates", "knowledge_points", "method_chains", "common_mistakes", "confidence")
        if safe_brief.get(key) not in (None, "", [], {})
    }


def _repair_message(
    *,
    plan: dict[str, Any],
    targets: list[QuestionRepairTarget],
    review_input: ReviewPlanInput,
    attempt: int,
    agent_blueprint: AgenticPlanBlueprint | None,
    prompt_bundle: PromptBundle,
    source_brief: ReviewPlanSourceBrief | None,
) -> str:
    normalized = normalize_final_review_plan(plan)
    lesson_info = normalized.get("lesson_info") if isinstance(normalized.get("lesson_info"), dict) else {}
    blueprint_payload = {}
    if agent_blueprint is not None:
        blueprint_payload = {
            "strategy_summary": agent_blueprint.strategy_summary,
            "student_diagnosis": agent_blueprint.student_diagnosis,
            "knowledge_map": agent_blueprint.knowledge_map[:8],
            "writer_instructions": agent_blueprint.writer_instructions[:8],
            "success_criteria": agent_blueprint.success_criteria[:8],
        }
    payload = {
        "attempt": attempt,
        "lesson": {
            "subject": review_input.subject or lesson_info.get("subject", ""),
            "grade": review_input.grade or lesson_info.get("grade", ""),
            "topic": review_input.topic or lesson_info.get("topic", ""),
            "weak_points": review_input.weak_points or normalized.get("weak_points_summary", ""),
            "review_days": review_input.review_days,
            "schedule_mode": review_input.schedule_mode,
            "user_requirements": review_input.user_requirements,
        },
        "full_review_topics": normalized.get("full_review_topics", [])[:10],
        "source_brief": _compact_source_brief(prompt_bundle, source_brief),
        "parent_blueprint": blueprint_payload,
        "targets": [
            {
                "target_id": target.target_id,
                "kind": target.kind,
                "day": target.day,
                "question_number": target.question_position + 1,
                "day_context": target.day_context,
                "issue": target.issue.model_dump(),
                "current_question": target.question,
            }
            for target in targets
        ],
    }
    return "\n\n".join(
        [
            "请只修复 targets 中列出的题目，返回 repairs，不要返回完整 plan。",
            "如果是数学题，必须先验算再确定答案；答案和解析必须一致。",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def _normalize_choice_repair(value: dict[str, Any]) -> dict[str, Any]:
    question = str(value.get("question") or value.get("stem") or "").strip()
    options = [str(option or "").strip() for option in value.get("options", []) if str(option or "").strip()]
    answer = str(value.get("answer") or "").strip()
    analysis = str(value.get("analysis") or value.get("explanation") or "").strip()
    if not question or len(options) < 4 or not answer:
        raise ValueError("choice repair must include question, 4 options, and answer")
    repaired = {"question": question, "options": options[:4], "answer": answer}
    if analysis:
        repaired["analysis"] = analysis
    return repaired


def _normalize_blank_repair(value: dict[str, Any]) -> dict[str, Any]:
    text = str(value.get("text") or value.get("question") or value.get("stem") or "").strip()
    answer = value.get("answer")
    if isinstance(answer, list):
        answer = "；".join(str(item).strip() for item in answer if str(item or "").strip())
    answer_text = str(answer or "").strip()
    if not text or not answer_text:
        raise ValueError("blank repair must include text and answer")
    return {"text": text, "answer": answer_text}


def _repairs_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    repairs = payload.get("repairs")
    if isinstance(repairs, list):
        return [repair for repair in repairs if isinstance(repair, dict)]
    if isinstance(payload.get("repair"), dict):
        return [payload["repair"]]
    if payload.get("target_id"):
        return [payload]
    return []


def _apply_repairs(plan: dict[str, Any], targets: list[QuestionRepairTarget], payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_final_review_plan(plan)
    repairs = {str(repair.get("target_id") or "").strip(): repair for repair in _repairs_from_payload(payload)}
    if len(repairs) < len(targets):
        raise ValueError("question repair response did not include every target")

    for target in targets:
        repair = repairs.get(target.target_id)
        if not isinstance(repair, dict):
            raise ValueError(f"missing repair for {target.target_id}")
        day = normalized["days"][target.day_position]
        if target.kind == "choice":
            day["choices"][target.question_position] = _normalize_choice_repair(repair)
        elif target.kind == "blank":
            day["blanks"][target.question_position] = _normalize_blank_repair(repair)
        else:
            raise ValueError(f"unsupported repair kind: {target.kind}")
    return normalized


def _apply_lesson_date(plan: dict[str, Any], review_input: ReviewPlanInput) -> dict[str, Any]:
    if review_input.lesson_date:
        plan.setdefault("lesson_info", {})["date"] = review_input.lesson_date
    else:
        plan.setdefault("lesson_info", {}).setdefault("date", str(date.today()))
    return plan


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[dict[str, Any], dict[str, Any]]:
    review_input: ReviewPlanInput = input_data["input"]
    prompt_bundle: PromptBundle = input_data["prompt_bundle"]
    quality: QualityReview = input_data["quality"]
    plan: dict[str, Any] = input_data["plan"]
    attempt = int(input_data.get("attempt") or 1)
    agent_blueprint: AgenticPlanBlueprint | None = input_data.get("agent_blueprint")
    source_brief: ReviewPlanSourceBrief | None = input_data.get("source_brief")
    targets = find_question_repair_targets(plan, quality)
    if not targets:
        raise ValueError("quality issues are not localizable to printable questions")

    writer_provider = resolve_review_plan_writer_provider()
    writer_model = resolve_review_plan_writer_model(provider=writer_provider)
    temperature = resolve_review_plan_repair_temperature()
    rendered = render_prompt(
        system_prompt_path=prompt_bundle.system_prompt_path,
        node_prompt_path="nodes/question-repair.md",
        subject_pack_path=prompt_bundle.subject_pack_path,
        style_path=prompt_bundle.style_path,
        rubric_path=prompt_bundle.rubric_path,
        variables={**prompt_bundle.variables, "revision_attempt": attempt, "stage": "question_repair"},
    )
    payload, usage = generate_review_plan_json(
        system_prompt=rendered["prompt"],
        user_message=_repair_message(
            plan=plan,
            targets=targets,
            review_input=review_input,
            attempt=attempt,
            agent_blueprint=agent_blueprint,
            prompt_bundle=prompt_bundle,
            source_brief=source_brief,
        ),
        provider=writer_provider,
        model=writer_model,
        temperature=temperature,
        stage="question_repair",
        timeout_seconds=45.0,
        max_retries=0,
    )
    repaired = _apply_lesson_date(_apply_repairs(plan, targets, payload), review_input)
    context.node_outputs["question_repair_model_config"] = {
        "provider": writer_provider,
        "model": writer_model,
        "temperature": temperature,
        "prompt_version": rendered["prompt_version"],
        "usage": usage,
    }
    context.node_outputs.setdefault("question_repair_attempts", []).append(
        {
            "attempt": attempt,
            "prompt_version": rendered["prompt_version"],
            "target_ids": [target.target_id for target in targets],
            "quality_score_before": quality.score,
            "provider": writer_provider,
            "model": writer_model,
            "temperature": temperature,
            "usage": usage,
        }
    )
    return repaired, usage


question_repair_node: WorkflowNode[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]] = WorkflowNode(
    name="question_repair",
    run=_run,
)
