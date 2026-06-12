from __future__ import annotations

from typing import Any, Optional, Tuple, Union

from .executor import run_workflow_node
from .nodes import (
    intake_normalizer_node,
    plan_generator_node,
    prompt_bundle_builder_node,
    scope_planner_node,
    source_analyzer_node,
    subject_router_node,
    task_blueprint_node,
    time_allocator_node,
)
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
        scope = run_workflow_node(
            scope_planner_node,
            {"input": review_input, "normalized": normalized, "route": route, "source": source},
            context,
        )
        time_allocation = run_workflow_node(
            time_allocator_node,
            {"normalized": normalized, "scope": scope},
            context,
        )
        task_blueprint = run_workflow_node(
            task_blueprint_node,
            {
                "normalized": normalized,
                "route": route,
                "source": source,
                "scope": scope,
                "time_allocation": time_allocation,
            },
            context,
        )
        prompt_bundle = run_workflow_node(
            prompt_bundle_builder_node,
            {
                "route": route,
                "source": source,
                "scope": scope,
                "time_allocation": time_allocation,
                "task_blueprint": task_blueprint,
            },
            context,
        )
        plan, usage = run_workflow_node(
            plan_generator_node,
            {
                "input": review_input,
                "normalized": normalized,
                "route": route,
                "source": source,
                "scope": scope,
                "time_allocation": time_allocation,
                "task_blueprint": task_blueprint,
                "prompt_bundle": prompt_bundle,
            },
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
