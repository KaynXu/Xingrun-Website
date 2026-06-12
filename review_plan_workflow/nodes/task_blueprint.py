from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import (
    NormalizedBrief,
    ScopePlan,
    SourceSummary,
    SubjectRoute,
    TaskBlueprint,
    TimeAllocation,
)
from review_plan_workflow.state import WorkflowContext


def _read_subject_pack(route: SubjectRoute) -> dict[str, Any]:
    if not route.subject_pack_path:
        return {}
    path = Path(route.subject_pack_path)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _default_task_blocks(subject: str) -> list[dict[str, Any]]:
    if subject == "physics":
        return [
            {"name": "概念和适用条件", "completion": "能用自己的话解释概念、公式适用条件和单位。"},
            {"name": "实验/图像题", "completion": "能读图、解释变量关系，并写出误差或实验注意点。"},
            {"name": "计算与文字说明", "completion": "能写出步骤、单位检查和最终解释。"},
        ]
    if subject == "ielts":
        return [
            {"name": "题型定位", "completion": "能说明题型步骤、定位词和同义替换。"},
            {"name": "错因复盘", "completion": "能归类错因并写出下一次避免方法。"},
            {"name": "限时训练", "completion": "在限定时间内完成并记录正确率。"},
        ]
    if subject == "math":
        return [
            {"name": "定义/模型复现", "completion": "能说清题型入口、关键公式或模型。"},
            {"name": "例题步骤卡", "completion": "能按步骤复述一道代表题的解法。"},
            {"name": "变式与错因", "completion": "完成同类变式并写出错因订正。"},
        ]
    return [
        {"name": "知识回看", "completion": "能复述核心知识点。"},
        {"name": "任务练习", "completion": "完成练习并记录错因。"},
    ]


def _run(input_data: dict[str, Any], context: WorkflowContext) -> TaskBlueprint:
    normalized: NormalizedBrief = input_data["normalized"]
    route: SubjectRoute = input_data["route"]
    source: SourceSummary = input_data["source"]
    scope: ScopePlan = input_data["scope"]
    time_allocation: TimeAllocation = input_data["time_allocation"]

    subject_pack = _read_subject_pack(route)
    required_components = subject_pack.get("required_components") or []
    if not isinstance(required_components, list):
        required_components = []

    risk_controls = [
        "不虚构考试日期、教材页码、学生成绩或官方要求。",
        "信息不足时写入 missingInfo、assumptions 或 warnings。",
        "每天任务必须有产出要求和完成标准。",
    ]
    if source.confidence < 0.6 or normalized.missing_info:
        risk_controls.append("低置信度输入下，避免给出过细的题号、页码或官方 syllabus 承诺。")

    return TaskBlueprint(
        subject=route.selected_subject,
        task_blocks=_default_task_blocks(route.selected_subject),
        required_components=[str(item) for item in required_components],
        output_contract={
            "review_days": scope.review_days,
            "daily_workload_minutes": time_allocation.daily_workload_minutes,
            "must_include_review_loop": bool(scope.review_loop),
            "module_sequence": scope.module_sequence,
        },
        risk_controls=risk_controls,
    )


task_blueprint_node: WorkflowNode[dict[str, Any], TaskBlueprint] = WorkflowNode(
    name="task_blueprint",
    run=_run,
)
