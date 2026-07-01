from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config_runtime import resolve_review_plan_temperature
from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm.client import generate_review_plan_json
from review_plan_workflow.llm.prompt_renderer import render_prompt
from review_plan_workflow.llm.prompt_registry import PROMPT_ROOT
from review_plan_workflow.schemas import (
    AgenticPlanBlueprint,
    NormalizedBrief,
    ReviewPlanInput,
    ReviewPlanSourceBrief,
    ScopePlan,
    SourceSummary,
    SubjectRoute,
    TaskBlueprint,
    TimeAllocation,
)
from review_plan_workflow.source_brief import source_brief_trace_payload, source_evidence_list_trace_payload
from review_plan_workflow.state import WorkflowContext


def _relative_prompt_path(path: str, fallback: str) -> str:
    if not path:
        return fallback
    try:
        resolved = PROMPT_ROOT.joinpath(path).resolve() if not path.startswith("/") else Path(path).resolve()
    except Exception:
        return fallback
    root = PROMPT_ROOT.resolve()
    if root in resolved.parents or resolved == root:
        return str(resolved.relative_to(root))
    return fallback


def _planner_message(
    *,
    review_input: ReviewPlanInput,
    normalized: NormalizedBrief,
    route: SubjectRoute,
    source: SourceSummary,
    scope: ScopePlan,
    time_allocation: TimeAllocation,
    task_blueprint: TaskBlueprint,
    source_brief: ReviewPlanSourceBrief | None = None,
) -> str:
    source_payload = source.model_dump()
    source_payload["evidence_map"] = source_evidence_list_trace_payload(source_payload.get("evidence_map"))
    if source.source_brief is not None:
        source_payload["source_brief"] = source_brief_trace_payload(source.source_brief)
    payload = {
        "input": {
            "subject": review_input.subject,
            "grade": review_input.grade,
            "topic": review_input.topic,
            "weak_points": review_input.weak_points,
            "lesson_date": review_input.lesson_date,
            "summary_text": review_input.summary_text,
            "schedule_mode": review_input.schedule_mode,
            "review_days": review_input.review_days,
            "user_requirements": review_input.user_requirements,
        },
        "normalized": normalized.model_dump(),
        "route": route.model_dump(),
        "source": source_payload,
        "source_brief": source_brief_trace_payload(source_brief or source.source_brief),
        "scope": scope.model_dump(),
        "time_allocation": time_allocation.model_dump(),
        "task_blueprint": task_blueprint.model_dump(),
    }
    output_contract = {
        "strategy_summary": "一句话说明本课复习策略，不写空话。",
        "student_diagnosis": ["学生最需要修复的认知断点或错因。"],
        "knowledge_map": [{"name": "知识点", "role": "为什么重要", "evidence": "来自课堂材料的证据"}],
        "day_strategies": [
            {
                "day": 1,
                "objective": "当天复习目的",
                "retrieval_focus": ["要主动回忆的内容"],
                "question_design": ["填空/选择/口述卡片该怎么设计"],
                "review_loop": ["复盘动作"],
                "risk_controls": ["避免空泛或虚构的约束"],
            }
        ],
        "writer_instructions": ["给 writer 的具体执行指令。"],
        "quality_risks": ["最容易导致低质量 PDF 的风险。"],
        "success_criteria": ["审稿时判断合格的标准。"],
        "assumptions": ["必要但不能伪装成事实的假设。"],
        "confidence": 0.0,
    }
    return "\n\n".join(
        [
            "你是父模型，只做任务分析、拆解和写作蓝图，不生成最终 PDF JSON。",
            "目标是让后续 writer 像 Codex 一样先理解再执行，而不是一次性套模板。",
            "请返回严格 JSON object，字段按 output_contract。",
            "output_contract:\n" + json.dumps(output_contract, ensure_ascii=False, indent=2),
            "workflow_input:\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[AgenticPlanBlueprint, dict[str, Any]]:
    review_input: ReviewPlanInput = input_data["input"]
    normalized: NormalizedBrief = input_data["normalized"]
    route: SubjectRoute = input_data["route"]
    source: SourceSummary = input_data["source"]
    scope: ScopePlan = input_data["scope"]
    time_allocation: TimeAllocation = input_data["time_allocation"]
    task_blueprint: TaskBlueprint = input_data["task_blueprint"]
    source_brief: ReviewPlanSourceBrief | None = input_data.get("source_brief")
    subject_pack_path = _relative_prompt_path(route.subject_pack_path or "", "subjects/common.yaml")
    temperature = resolve_review_plan_temperature()

    rendered = render_prompt(
        system_prompt_path="system/review-plan-agent.md",
        node_prompt_path="nodes/parent-planner.md",
        subject_pack_path=subject_pack_path,
        style_path="styles/review_plan_style.yaml",
        rubric_path="rubrics/review-plan-quality.yaml",
        variables={
            "trace_id": context.trace_id,
            "selected_subject": route.selected_subject,
            "stage": "parent_planner",
        },
    )
    payload, usage = generate_review_plan_json(
        system_prompt=rendered["prompt"],
        user_message=_planner_message(
            review_input=review_input,
            normalized=normalized,
            route=route,
            source=source,
            scope=scope,
            time_allocation=time_allocation,
            task_blueprint=task_blueprint,
            source_brief=source_brief,
        ),
        provider=context.provider,
        model=context.model,
        reasoning_effort=context.reasoning_effort,
        temperature=temperature,
        stage="parent_planner",
        timeout_seconds=120.0,
        max_retries=0,
    )
    raw_blueprint = payload
    for wrapper_key in ("agenticPlanBlueprint", "blueprint", "plan_blueprint"):
        if isinstance(payload.get(wrapper_key), dict):
            raw_blueprint = payload[wrapper_key]
            break
    blueprint = AgenticPlanBlueprint.model_validate(raw_blueprint)
    context.node_outputs["parent_planner_model_config"] = {
        "provider": context.provider,
        "model": context.model,
        "reasoning_effort": context.reasoning_effort,
        "temperature": temperature,
        "prompt_version": rendered["prompt_version"],
        "usage": usage,
    }
    return blueprint, usage


parent_planner_node: WorkflowNode[dict[str, Any], tuple[AgenticPlanBlueprint, dict[str, Any]]] = WorkflowNode(
    name="parent_planner",
    run=_run,
)
