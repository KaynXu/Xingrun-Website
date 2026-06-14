from __future__ import annotations

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, SourceSummary
from review_plan_workflow.state import WorkflowContext


def _run(input_data: NormalizedBrief, context: WorkflowContext) -> SourceSummary:
    text = "\n".join(input_data.materials).strip()
    confirmed_topics: list[str] = []
    if text:
        for marker in ("本节课主题：", "主题：", "topic:"):
            if marker in text:
                confirmed_topics.append(text.split(marker, 1)[1].splitlines()[0].strip())
                break
    if not confirmed_topics and input_data.known_weaknesses:
        confirmed_topics.extend(input_data.known_weaknesses)

    risk_notes = []
    if not text:
        risk_notes.append("没有课堂材料，无法做证据映射。")
    if input_data.confidence < 0.7:
        risk_notes.append("输入信息不足，后续计划需要保留 assumptions/warnings。")

    if risk_notes:
        context.add_warning("source_confidence", "；".join(risk_notes), "medium")

    return SourceSummary(
        source_type="user_input" if text else "insufficient",
        confirmed_topics=confirmed_topics,
        assumed_topics=[] if confirmed_topics else ["根据主题和薄弱点生成低置信度范围"],
        evidence_map=[{"source": "summary_text", "evidence": text[:500]}] if text else [],
        risk_notes=risk_notes,
        confidence=0.8 if text else 0.3,
    )


source_analyzer_node: WorkflowNode[NormalizedBrief, SourceSummary] = WorkflowNode(
    name="source_analyzer",
    run=_run,
)
