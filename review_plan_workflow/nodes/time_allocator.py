from __future__ import annotations

from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, ScopePlan, TimeAllocation
from review_plan_workflow.state import WorkflowContext


DAY_LABELS = {
    1: "第1天复习",
    2: "隔天回看",
    7: "一周巩固",
    14: "两周混合",
    30: "月度回炉",
}


def _run(input_data: dict[str, Any], context: WorkflowContext) -> TimeAllocation:
    normalized: NormalizedBrief = input_data["normalized"]
    scope: ScopePlan = input_data["scope"]

    workload_minutes = 30
    availability = normalized.availability or {}
    if isinstance(availability.get("dailyMinutes"), int):
        workload_minutes = max(10, min(90, int(availability["dailyMinutes"])))

    review_schedule: list[dict[str, Any]] = []
    for day in scope.review_days:
        label = "第1天集中复习" if scope.review_days == [1] and day == 1 else DAY_LABELS.get(day, f"第 {day} 天复习")
        review_schedule.append(
            {
                "day": day,
                "label": label,
                "target_minutes": workload_minutes,
                "focus": " + ".join(scope.review_loop[:2]) if day in {1, 2} else " + ".join(scope.review_loop[-2:]),
            }
        )

    warnings: list[str] = []
    if workload_minutes < 20:
        warnings.append("每日可用时间很少，任务需要压缩为核心概念和关键错因。")
    if scope.confidence < 0.6:
        warnings.append("范围置信度偏低，时间分配必须保留教师二次确认空间。")
    for warning in warnings:
        context.add_warning("time_allocation", warning, "medium")

    return TimeAllocation(
        total_days=max(scope.review_days or [30]),
        review_schedule=review_schedule,
        daily_workload_minutes=workload_minutes,
        buffer_strategy="每个复习日保留 20% 时间用于错因订正和老师二次调整。",
        workload_warnings=warnings,
    )


time_allocator_node: WorkflowNode[dict[str, Any], TimeAllocation] = WorkflowNode(
    name="time_allocator",
    run=_run,
)
