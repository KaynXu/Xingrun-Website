from __future__ import annotations

from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, ReviewPlanInput, ReviewPlanSourceBrief
from review_plan_workflow.source_brief import build_deterministic_source_brief, source_brief_trace_payload
from review_plan_workflow.source_pack import build_lesson_source_pack, source_pack_trace_payload
from review_plan_workflow.state import WorkflowContext


def _trace_safe_source_brief(brief: ReviewPlanSourceBrief) -> dict[str, Any]:
    return source_brief_trace_payload(brief)


def _run(input_data: dict[str, Any], context: WorkflowContext) -> ReviewPlanSourceBrief:
    review_input: ReviewPlanInput = input_data["input"]
    normalized: NormalizedBrief = input_data["normalized"]
    if review_input.source_pack is not None:
        context.node_outputs["source_pack"] = source_pack_trace_payload(review_input.source_pack)
        raw_text = "\n".join(segment.text for segment in review_input.source_pack.segments).strip() or review_input.summary_text
    else:
        raw_text = "\n\n".join(normalized.materials).strip() or review_input.summary_text
        source_pack = build_lesson_source_pack(
            raw_text=raw_text,
            source_type="text",
            title=review_input.topic,
            subject=review_input.subject,
            topic=review_input.topic,
            weak_points=review_input.weak_points,
            user_requirements=review_input.user_requirements,
        )
        context.node_outputs["source_pack"] = source_pack_trace_payload(source_pack)
    brief = build_deterministic_source_brief(
        raw_text=raw_text,
        subject=review_input.subject,
        topic=review_input.topic,
        weak_points=review_input.weak_points,
        user_requirements=review_input.user_requirements,
    )
    context.node_outputs["source_brief"] = _trace_safe_source_brief(brief)
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
    output_serializer=_trace_safe_source_brief,
)
