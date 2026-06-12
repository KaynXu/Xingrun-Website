from __future__ import annotations

from datetime import date
from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm.client import generate_review_plan_json
from review_plan_workflow.schemas import PromptBundle, ReviewPlanInput
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


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[dict[str, Any], dict[str, Any]]:
    review_input: ReviewPlanInput = input_data["input"]
    prompt_bundle: PromptBundle = input_data["prompt_bundle"]
    plan, usage = generate_review_plan_json(
        system_prompt=prompt_bundle.prompt,
        user_message=_user_message(review_input, prompt_bundle),
        provider=context.provider,
        model=context.model,
    )
    if review_input.lesson_date:
        plan.setdefault("lesson_info", {})["date"] = review_input.lesson_date
    else:
        plan.setdefault("lesson_info", {}).setdefault("date", str(date.today()))
    return plan, usage


plan_generator_node: WorkflowNode[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]] = WorkflowNode(
    name="plan_generator",
    run=_run,
)
