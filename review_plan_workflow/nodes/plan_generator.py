from __future__ import annotations

import json
from datetime import date
from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm.client import generate_review_plan_json, merge_usage
from review_plan_workflow.schemas import PromptBundle, ReviewPlanInput, validate_final_review_plan
from review_plan_workflow.state import WorkflowContext


def _user_message(review_input: ReviewPlanInput, prompt_bundle: PromptBundle) -> str:
    meta_parts = [f"生成日期（第0天）：{date.today().isoformat()}"]
    if review_input.subject:
        meta_parts.append(f"科目：{review_input.subject}")
    if review_input.grade:
        meta_parts.append(f"年级：{review_input.grade}")
    if review_input.topic:
        meta_parts.append(f"本节课主题：{review_input.topic}")
    if review_input.weak_points:
        meta_parts.append(f"学生薄弱点：{review_input.weak_points}")
    if review_input.lesson_date:
        meta_parts.append(f"上课日期：{review_input.lesson_date}")

    return "\n\n".join(
        [
            "\n".join(meta_parts),
            "已校验工作流上下文：\n" + str(prompt_bundle.variables),
            "课堂总结：\n" + review_input.summary_text,
            "请返回可直接进入现有 PDF 渲染链路的 JSON object，不要输出 Markdown 包裹。",
        ]
    )


def _apply_lesson_date(plan: dict[str, Any], review_input: ReviewPlanInput) -> dict[str, Any]:
    if review_input.lesson_date:
        plan.setdefault("lesson_info", {})["date"] = review_input.lesson_date
    else:
        plan.setdefault("lesson_info", {}).setdefault("date", str(date.today()))
    return plan


def _schema_errors(plan: dict[str, Any]) -> list[str]:
    _, errors = validate_final_review_plan(plan)
    return errors


def _repair_message(
    *,
    original_message: str,
    invalid_plan: dict[str, Any] | None,
    errors: list[str],
    parse_error: str = "",
) -> str:
    sections = [
        "上一轮复习计划 JSON 未通过结构检查。请只修复 JSON/schema 问题，不扩写未提供的信息。",
        "必须返回完整 JSON object，不要 Markdown，不要解释。",
        "days 必须且只能覆盖 day=1,2,7,14,30；每个 day 必须有可打印的复习任务。",
    ]
    if parse_error:
        sections.append("JSON 解析错误：\n" + parse_error)
    if errors:
        sections.append("Schema 错误：\n" + "\n".join(f"- {error}" for error in errors))
    if invalid_plan is not None:
        sections.append("上一轮已解析 JSON：\n" + json.dumps(invalid_plan, ensure_ascii=False, indent=2))
    sections.append("原始生成请求：\n" + original_message)
    return "\n\n".join(sections)


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[dict[str, Any], dict[str, Any]]:
    review_input: ReviewPlanInput = input_data["input"]
    prompt_bundle: PromptBundle = input_data["prompt_bundle"]
    user_message = _user_message(review_input, prompt_bundle)
    attempts: list[dict[str, Any]] = []
    plan: dict[str, Any] | None = None
    usage: dict[str, Any] = {}
    parse_error = ""
    errors: list[str] = []

    try:
        plan, usage = generate_review_plan_json(
            system_prompt=prompt_bundle.prompt,
            user_message=user_message,
            provider=context.provider,
            model=context.model,
        )
        _apply_lesson_date(plan, review_input)
        errors = _schema_errors(plan)
        attempts.append({"attempt": 1, "stage": "generate", "schema_errors": errors})
    except ValueError as exc:
        parse_error = str(exc)
        attempts.append({"attempt": 1, "stage": "generate", "error": parse_error})

    if parse_error or errors:
        context.add_warning(
            "plan_generator_schema_repair_retry",
            "计划生成结果未通过 JSON/schema 检查，已触发一次结构修复重试。",
            "medium",
        )
        try:
            repaired, repair_usage = generate_review_plan_json(
                system_prompt=prompt_bundle.prompt
                + "\n\n# Schema Repair\n只修复 JSON 和 schema 结构问题，保留已正确的教学内容。",
                user_message=_repair_message(
                    original_message=user_message,
                    invalid_plan=plan,
                    errors=errors,
                    parse_error=parse_error,
                ),
                provider=context.provider,
                model=context.model,
            )
            plan = _apply_lesson_date(repaired, review_input)
            usage = merge_usage(usage, repair_usage)
            repair_errors = _schema_errors(plan)
            attempts.append({"attempt": 2, "stage": "schema_repair", "schema_errors": repair_errors})
        except Exception as exc:
            if plan is None:
                raise
            repair_errors = errors
            attempts.append({"attempt": 2, "stage": "schema_repair", "error": str(exc)})
        if repair_errors:
            context.add_warning(
                "plan_generator_schema_repair_failed",
                "结构修复后仍未完全通过 schema，后续质量门禁将继续处理。",
                "high",
            )

    context.node_outputs["plan_generator_attempts"] = attempts
    if plan is None:
        raise ValueError("plan_generator did not produce a review plan")
    return plan, usage


plan_generator_node: WorkflowNode[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]] = WorkflowNode(
    name="plan_generator",
    run=_run,
)
