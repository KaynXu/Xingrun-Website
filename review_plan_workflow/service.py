from __future__ import annotations

from typing import Any, Optional, Tuple, Union

from .executor import WorkflowNode, run_workflow_node
from .nodes import intake_normalizer_node, source_analyzer_node, subject_router_node
from .quality_gate import review_single_lesson_plan
from .revision_policy import apply_revision_policy
from .schemas import ReviewPlanInput
from .state import WorkflowContext


def _record_run(
    *,
    lesson_id: int,
    organization_id: int,
    context: WorkflowContext,
    status: str,
    quality_review: Optional[dict[str, Any]] = None,
) -> None:
    if not lesson_id or not organization_id:
        return
    try:
        from lesson_manager import save_review_plan_run

        save_review_plan_run(
            lesson_id=lesson_id,
            organization_id=organization_id,
            trace_id=context.trace_id,
            status=status,
            subject=context.subject,
            provider=context.provider,
            model=context.model,
            prompt_version=context.prompt_version,
            style_version=context.style_version,
            schema_version=context.schema_version,
            warnings=context.warnings_as_dicts(),
            quality_review=quality_review or {},
            node_outputs=context.node_outputs,
            logs=context.logs_as_dicts(),
        )
    except Exception:
        # Trace storage must never make the existing generation path fail.
        return


def _legacy_plan_generator(payload: dict[str, Any], context: WorkflowContext) -> tuple[dict[str, Any], dict[str, Any]]:
    import ai_processor

    result = ai_processor.parse_and_generate_plan(
        summary_text=payload["input"].summary_text,
        subject=payload["input"].subject,
        grade=payload["input"].grade,
        topic=payload["input"].topic,
        weak_points=payload["input"].weak_points,
        lesson_date=payload["input"].lesson_date,
        include_usage=True,
    )
    if isinstance(result, tuple) and len(result) == 2:
        plan, usage = result
    else:
        plan, usage = result, {}
    return plan, usage


plan_generator_node: WorkflowNode[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]] = WorkflowNode(
    name="plan_generator",
    run=_legacy_plan_generator,
)


def generate_single_lesson_review_plan(
    *,
    summary_text: str,
    subject: str = "",
    grade: str = "",
    topic: str = "",
    weak_points: str = "",
    lesson_date: str = "",
    provider: str = "",
    model: str = "",
    lesson_id: int = 0,
    organization_id: int = 0,
    include_usage: bool = False,
) -> Union[dict[str, Any], Tuple[dict[str, Any], dict[str, Any]]]:
    context = WorkflowContext(provider=provider, model=model)
    review_input = ReviewPlanInput(
        summary_text=summary_text,
        subject=subject,
        grade=grade,
        topic=topic,
        weak_points=weak_points,
        lesson_date=lesson_date,
    )
    _record_run(lesson_id=lesson_id, organization_id=organization_id, context=context, status="running")

    try:
        normalized = run_workflow_node(intake_normalizer_node, review_input, context)
        route = run_workflow_node(subject_router_node, normalized, context)
        source = run_workflow_node(source_analyzer_node, normalized, context)
        plan, usage = run_workflow_node(
            plan_generator_node,
            {"input": review_input, "normalized": normalized, "route": route, "source": source},
            context,
        )
        quality = review_single_lesson_plan(plan, subject=route.selected_subject)
        context.node_outputs["quality_reviewer"] = quality.model_dump()
        if quality.must_revise:
            plan = apply_revision_policy(plan, quality, context)

        _record_run(
            lesson_id=lesson_id,
            organization_id=organization_id,
            context=context,
            status="succeeded",
            quality_review=quality.model_dump(),
        )
        if include_usage:
            return plan, usage
        return plan
    except Exception:
        _record_run(lesson_id=lesson_id, organization_id=organization_id, context=context, status="failed")
        raise
