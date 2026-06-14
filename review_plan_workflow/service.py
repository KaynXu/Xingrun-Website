from __future__ import annotations

from typing import Any, Optional, Tuple, Union

from config_runtime import resolve_review_plan_model, resolve_review_plan_provider

from .executor import run_workflow_node
from .nodes import (
    intake_normalizer_node,
    plan_generator_node,
    prompt_bundle_builder_node,
    revision_node,
    scope_planner_node,
    source_analyzer_node,
    subject_router_node,
    task_blueprint_node,
    time_allocator_node,
)
from .quality_gate import review_single_lesson_plan
from .llm.client import merge_usage
from .schemas import QualityReview, ReviewPlanInput
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


def _score_quality(plan: dict[str, Any], *, subject: str, context: WorkflowContext, node_key: str) -> QualityReview:
    quality = review_single_lesson_plan(plan, subject=subject)
    context.node_outputs[node_key] = quality.model_dump()
    context.node_outputs["quality_reviewer"] = quality.model_dump()
    return quality


def _maybe_revise_plan(
    *,
    plan: dict[str, Any],
    quality: QualityReview,
    usage: dict[str, Any],
    review_input: ReviewPlanInput,
    prompt_bundle: Any,
    subject: str,
    context: WorkflowContext,
) -> tuple[dict[str, Any], QualityReview, dict[str, Any]]:
    if not quality.must_revise:
        return plan, quality, usage

    best_plan = plan
    best_quality = quality
    current_plan = plan
    current_quality = quality
    total_usage = usage

    for attempt in range(1, 3):
        try:
            revised_plan, revision_usage = run_workflow_node(
                revision_node,
                {
                    "input": review_input,
                    "prompt_bundle": prompt_bundle,
                    "plan": current_plan,
                    "quality": current_quality,
                    "attempt": attempt,
                },
                context,
            )
        except Exception as exc:
            context.add_warning(
                "quality_revision_failed",
                f"第 {attempt} 次质量修订失败，已返回当前最优结果：{exc}",
                "high",
            )
            break

        total_usage = merge_usage(total_usage, revision_usage)
        current_plan = revised_plan
        current_quality = _score_quality(
            current_plan,
            subject=subject,
            context=context,
            node_key=f"quality_reviewer_after_revision_{attempt}",
        )
        if current_quality.score >= best_quality.score:
            best_plan = current_plan
            best_quality = current_quality
        if not current_quality.must_revise:
            return current_plan, current_quality, total_usage

    if best_quality.must_revise:
        context.add_warning(
            "quality_revision_required",
            "质量门禁在最多 2 次 revision 后仍建议人工复核；已返回当前最高分版本。",
            "high",
        )
    return best_plan, best_quality, total_usage


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
    resolved_provider = provider or resolve_review_plan_provider()
    resolved_model = model or resolve_review_plan_model(provider=resolved_provider)
    context = WorkflowContext(provider=resolved_provider, model=resolved_model)
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
        quality = _score_quality(plan, subject=route.selected_subject, context=context, node_key="quality_reviewer_initial")
        plan, quality, usage = _maybe_revise_plan(
            plan=plan,
            quality=quality,
            usage=usage,
            review_input=review_input,
            prompt_bundle=prompt_bundle,
            subject=route.selected_subject,
            context=context,
        )

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
