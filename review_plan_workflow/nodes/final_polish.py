from __future__ import annotations

import json
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
    ReviewPlanInput,
    ReviewPlanSourceBrief,
    normalize_final_review_plan,
)
from review_plan_workflow.source_brief import source_brief_trace_payload
from review_plan_workflow.state import WorkflowContext


FINAL_POLISH_TIMEOUT_SECONDS = 60.0


def _final_polish_message(
    *,
    plan: dict[str, Any],
    review_input: ReviewPlanInput,
    prompt_bundle: PromptBundle,
    agent_blueprint: AgenticPlanBlueprint | None,
    source_brief: ReviewPlanSourceBrief | None,
) -> str:
    safe_brief = prompt_bundle.variables.get("source_brief")
    if not isinstance(safe_brief, dict) and source_brief is not None:
        safe_brief = source_brief_trace_payload(source_brief, subject_key=review_input.subject)
    sections = [
        "这份复习计划已经通过质量门禁。请只做最终成品润色，不做结构性重写。",
        "必须保留原计划所有可打印题目的数量、题型、答案事实和课堂关键链路。",
        "如果发现数学裸文本，改成标准 LaTeX；例如 tanalpha=(1)/(2) 改成 $\\tan\\alpha=\\frac{1}{2}$，tan(alpha+beta)=1 改成 $\\tan(\\alpha+\\beta)=1$。",
        "返回完整 JSON object；不要返回解释、Markdown、diff 或 patch。",
        "trusted_workflow_metadata:\n"
        + json.dumps(
            {
                "subject": review_input.subject,
                "grade": review_input.grade,
                "lesson_date": review_input.lesson_date,
                "schedule_mode": review_input.schedule_mode,
                "review_days": review_input.review_days,
                "daily_count": review_input.daily_count,
                "constraints": review_input.constraints,
            },
            ensure_ascii=False,
            indent=2,
        ),
    ]
    if review_input.user_requirements:
        sections.append(
            "老师本次生成要求（不得突破题量、事实、schema、PDF 安全和质量门禁硬规则）："
            + review_input.user_requirements
        )
    if agent_blueprint is not None:
        sections.append("父模型教学蓝图（仅用于保持知识链路，不得新增事实）：\n" + agent_blueprint.model_dump_json(indent=2))
    if isinstance(safe_brief, dict) and safe_brief:
        sections.append("结构化课堂材料摘要（只用于防止润色时删掉关键链路）：\n" + json.dumps(safe_brief, ensure_ascii=False, indent=2))
    sections.append("当前已通过计划 JSON：\n" + json.dumps(plan, ensure_ascii=False, indent=2))
    return "\n\n".join(sections)


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[dict[str, Any], dict[str, Any]]:
    review_input: ReviewPlanInput = input_data["input"]
    prompt_bundle: PromptBundle = input_data["prompt_bundle"]
    plan: dict[str, Any] = input_data["plan"]
    agent_blueprint: AgenticPlanBlueprint | None = input_data.get("agent_blueprint")
    source_brief: ReviewPlanSourceBrief | None = input_data.get("source_brief")
    writer_provider = resolve_review_plan_writer_provider()
    writer_model = resolve_review_plan_writer_model(provider=writer_provider)
    temperature = resolve_review_plan_repair_temperature()

    rendered = render_prompt(
        system_prompt_path=prompt_bundle.system_prompt_path,
        node_prompt_path="nodes/final-polish.md",
        subject_pack_path=prompt_bundle.subject_pack_path,
        style_path=prompt_bundle.style_path,
        rubric_path=prompt_bundle.rubric_path,
        variables={**prompt_bundle.variables, "stage": "final_polish"},
    )
    polished, usage = generate_review_plan_json(
        system_prompt=rendered["prompt"],
        user_message=_final_polish_message(
            plan=plan,
            review_input=review_input,
            prompt_bundle=prompt_bundle,
            agent_blueprint=agent_blueprint,
            source_brief=source_brief,
        ),
        provider=writer_provider,
        model=writer_model,
        temperature=temperature,
        stage="final_polish",
        timeout_seconds=FINAL_POLISH_TIMEOUT_SECONDS,
        max_retries=0,
    )
    polished = normalize_final_review_plan(polished)
    context.node_outputs["final_polish_model_config"] = {
        "provider": writer_provider,
        "model": writer_model,
        "temperature": temperature,
        "timeout_seconds": FINAL_POLISH_TIMEOUT_SECONDS,
        "prompt_version": rendered["prompt_version"],
        "usage": usage,
    }
    return polished, usage


final_polish_node: WorkflowNode[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]] = WorkflowNode(
    name="final_polish",
    run=_run,
)
