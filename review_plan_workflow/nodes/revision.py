from __future__ import annotations

import json
from datetime import date
from typing import Any

from config_runtime import resolve_review_plan_temperature
from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm.client import generate_review_plan_json
from review_plan_workflow.llm.prompt_renderer import render_prompt
from review_plan_workflow.schemas import (
    AgenticPlanBlueprint,
    PromptBundle,
    QualityReview,
    ReviewPlanInput,
    normalize_final_review_plan,
)
from review_plan_workflow.state import WorkflowContext


def _apply_lesson_date(plan: dict[str, Any], review_input: ReviewPlanInput) -> dict[str, Any]:
    if review_input.lesson_date:
        plan.setdefault("lesson_info", {})["date"] = review_input.lesson_date
    else:
        plan.setdefault("lesson_info", {}).setdefault("date", str(date.today()))
    return plan


def _revision_message(
    *,
    plan: dict[str, Any],
    quality: QualityReview,
    review_input: ReviewPlanInput,
    attempt: int,
    agent_blueprint: AgenticPlanBlueprint | None = None,
) -> str:
    sections = [
        f"Targeted revision attempt: {attempt}/2",
        "只修复 quality review 指出的问题；保留原计划中已经正确的结构和内容。",
        "不得虚构教材页码、考试日期、学生成绩、老师原话或未提供的题目来源。",
        f"必须返回完整 JSON object，且 days 只包含 {review_input.review_days} 的复习节点。",
        "选择题硬修复：逐日检查 choices；任何 options 只写 A/B/C/D、少于 4 个完整选项或 answer 为空时，必须重写为完整 question + A-D 四个具体选项 + 单字母答案。",
    ]
    if review_input.user_requirements:
        sections.append(
            "老师本次生成要求（只能在结构、事实、schema、PDF 和质量门禁硬规则内执行）："
            + review_input.user_requirements
        )
    if agent_blueprint is not None:
        sections.append("父模型教学蓝图：\n" + agent_blueprint.model_dump_json(indent=2))
    sections.extend(
        [
            "质量问题：\n" + quality.model_dump_json(indent=2),
            "用户输入：\n"
            + json.dumps(
                {
                    "subject": review_input.subject,
                    "grade": review_input.grade,
                    "topic": review_input.topic,
                    "weak_points": review_input.weak_points,
                    "lesson_date": review_input.lesson_date,
                    "schedule_mode": review_input.schedule_mode,
                    "review_days": review_input.review_days,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "当前计划 JSON：\n" + json.dumps(plan, ensure_ascii=False, indent=2),
        ]
    )
    return "\n\n".join(sections)


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[dict[str, Any], dict[str, Any]]:
    review_input: ReviewPlanInput = input_data["input"]
    prompt_bundle: PromptBundle = input_data["prompt_bundle"]
    quality: QualityReview = input_data["quality"]
    plan: dict[str, Any] = input_data["plan"]
    attempt = int(input_data.get("attempt") or 1)
    agent_blueprint: AgenticPlanBlueprint | None = input_data.get("agent_blueprint")
    temperature = resolve_review_plan_temperature()

    rendered = render_prompt(
        system_prompt_path=prompt_bundle.system_prompt_path,
        node_prompt_path="nodes/revision.md",
        subject_pack_path=prompt_bundle.subject_pack_path,
        style_path=prompt_bundle.style_path,
        rubric_path=prompt_bundle.rubric_path,
        variables={**prompt_bundle.variables, "revision_attempt": attempt},
    )
    revised, usage = generate_review_plan_json(
        system_prompt=rendered["prompt"],
        user_message=_revision_message(
            plan=plan,
            quality=quality,
            review_input=review_input,
            attempt=attempt,
            agent_blueprint=agent_blueprint,
        ),
        provider=context.provider,
        model=context.model,
        reasoning_effort=context.reasoning_effort,
        temperature=temperature,
        stage="targeted_revision",
    )
    revised = _apply_lesson_date(normalize_final_review_plan(revised), review_input)
    context.node_outputs.setdefault("revision_attempts", []).append(
        {
            "attempt": attempt,
            "prompt_version": rendered["prompt_version"],
            "quality_score_before": quality.score,
            "issue_count": len(quality.issues),
            "temperature": temperature,
            "usage": usage,
        }
    )
    return revised, usage


revision_node: WorkflowNode[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]] = WorkflowNode(
    name="revision",
    run=_run,
)
