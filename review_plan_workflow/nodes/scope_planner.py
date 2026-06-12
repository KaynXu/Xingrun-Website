from __future__ import annotations

from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, ScopePlan, SourceSummary, SubjectRoute
from review_plan_workflow.state import WorkflowContext


def _topic_modules(normalized: NormalizedBrief, source: SourceSummary) -> list[str]:
    modules: list[str] = []
    modules.extend(topic for topic in source.confirmed_topics if topic)
    modules.extend(weakness for weakness in normalized.known_weaknesses if weakness)
    if not modules and source.assumed_topics:
        modules.extend(source.assumed_topics)
    return modules[:6]


def _subject_review_loop(subject: str) -> list[str]:
    if subject == "physics":
        return ["概念复述", "公式与单位检查", "实验/图像解释", "错因复盘", "混合自测"]
    if subject == "ielts":
        return ["题型定位", "错因分类", "同义替换积累", "限时练习", "复盘改写"]
    if subject == "math":
        return ["定义/模型回看", "例题步骤复述", "错因归类", "变式训练", "限时自测"]
    return ["知识点回看", "任务练习", "错因复盘", "自测检查"]


def _run(input_data: dict[str, Any], context: WorkflowContext) -> ScopePlan:
    normalized: NormalizedBrief = input_data["normalized"]
    route: SubjectRoute = input_data["route"]
    source: SourceSummary = input_data["source"]

    module_sequence = _topic_modules(normalized, source)
    scope_warnings = list(source.risk_notes)
    assumptions = list(normalized.assumptions)
    if not module_sequence:
        module_sequence = ["根据课堂主题和薄弱点确定复习范围"]
        scope_warnings.append("范围信息不足，只能生成低置信度复习模块。")
    if route.selected_subject == "unknown":
        scope_warnings.append("未识别学科，范围规划仅使用通用复习规则。")

    for warning in scope_warnings:
        context.add_warning("scope_planning", warning, "medium")

    return ScopePlan(
        review_days=[1, 2, 7, 14, 30],
        module_sequence=module_sequence,
        review_loop=_subject_review_loop(route.selected_subject),
        scope_warnings=scope_warnings,
        assumptions=assumptions,
        confidence=min(normalized.confidence, source.confidence),
    )


scope_planner_node: WorkflowNode[dict[str, Any], ScopePlan] = WorkflowNode(
    name="scope_planner",
    run=_run,
)
