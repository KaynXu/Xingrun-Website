from __future__ import annotations

from pathlib import Path
from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm import PromptRegistry, render_prompt
from review_plan_workflow.llm.prompt_registry import PROMPT_ROOT
from review_plan_workflow.schemas import (
    AgenticPlanBlueprint,
    PromptBundle,
    ScopePlan,
    SourceSummary,
    SubjectRoute,
    TaskBlueprint,
    TimeAllocation,
)
from review_plan_workflow.state import WorkflowContext


def _relative_prompt_path(path: str, fallback: str) -> str:
    if not path:
        return fallback
    resolved = Path(path).resolve()
    root = PROMPT_ROOT.resolve()
    if root in resolved.parents or resolved == root:
        return str(resolved.relative_to(root))
    return fallback


def _run(input_data: dict[str, Any], context: WorkflowContext) -> PromptBundle:
    route: SubjectRoute = input_data["route"]
    source: SourceSummary = input_data["source"]
    scope: ScopePlan = input_data["scope"]
    time_allocation: TimeAllocation = input_data["time_allocation"]
    task_blueprint: TaskBlueprint = input_data["task_blueprint"]
    agent_blueprint: AgenticPlanBlueprint | None = input_data.get("agent_blueprint")

    subject_pack_path = _relative_prompt_path(route.subject_pack_path or "", "subjects/common.yaml")
    variables = {
        "trace_id": context.trace_id,
        "selected_subject": route.selected_subject,
        "source": source.model_dump(),
        "scope": scope.model_dump(),
        "time_allocation": time_allocation.model_dump(),
        "task_blueprint": task_blueprint.model_dump(),
    }
    if agent_blueprint is not None:
        variables["agent_blueprint"] = agent_blueprint.model_dump()
    rendered = render_prompt(
        system_prompt_path="system/review-plan-agent.md",
        node_prompt_path="nodes/task-generator.md",
        subject_pack_path=subject_pack_path,
        style_path="styles/review_plan_style.yaml",
        rubric_path="rubrics/review-plan-quality.yaml",
        variables=variables,
        registry=PromptRegistry(),
    )
    context.prompt_version = rendered["prompt_version"]
    return PromptBundle(
        system_prompt_path="system/review-plan-agent.md",
        node_prompt_path="nodes/task-generator.md",
        subject_pack_path=subject_pack_path,
        style_path="styles/review_plan_style.yaml",
        rubric_path="rubrics/review-plan-quality.yaml",
        prompt_version=rendered["prompt_version"],
        prompt=rendered["prompt"],
        prompt_preview=rendered["prompt"][:1200],
        variables=variables,
    )


prompt_bundle_builder_node: WorkflowNode[dict[str, Any], PromptBundle] = WorkflowNode(
    name="prompt_bundle_builder",
    run=_run,
)
