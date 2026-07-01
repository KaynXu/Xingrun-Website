from __future__ import annotations

from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, ReviewPlanInput, ReviewPlanSourceBrief
from review_plan_workflow.source_brief import build_deterministic_source_brief
from review_plan_workflow.state import WorkflowContext


def _run(input_data: dict[str, Any], context: WorkflowContext) -> ReviewPlanSourceBrief:
    review_input: ReviewPlanInput = input_data["input"]
    normalized: NormalizedBrief = input_data["normalized"]
    raw_text = "\n\n".join(normalized.materials).strip() or review_input.summary_text
    brief = build_deterministic_source_brief(
        raw_text=raw_text,
        subject=review_input.subject,
        topic=review_input.topic,
        weak_points=review_input.weak_points,
        user_requirements=review_input.user_requirements,
    )
    context.node_outputs["source_brief"] = {
        **brief.model_dump(exclude={"cleaned_text"}),
        "cleaned_text_length": len(brief.cleaned_text),
    }
    if brief.missing_fields:
        context.add_warning(
            "source_brief_missing_fields",
            "结构化课堂材料缺少字段：" + "、".join(brief.missing_fields),
            "medium",
        )
    return brief


source_brief_builder_node: WorkflowNode[dict[str, Any], ReviewPlanSourceBrief] = WorkflowNode(
    name="source_brief_builder",
    run=_run,
)
