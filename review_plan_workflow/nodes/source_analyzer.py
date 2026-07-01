from __future__ import annotations

from typing import Any

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, ReviewPlanSourceBrief, SourceSummary
from review_plan_workflow.source_brief import source_brief_trace_payload, source_evidence_list_trace_payload
from review_plan_workflow.state import WorkflowContext


def _source_summary_trace_payload(source: SourceSummary) -> dict[str, Any]:
    payload = source.model_dump()
    payload["evidence_map"] = source_evidence_list_trace_payload(payload.get("evidence_map"))
    if source.source_brief is not None:
        payload["source_brief"] = source_brief_trace_payload(source.source_brief)
    return payload


def _run(input_data: dict[str, object] | NormalizedBrief, context: WorkflowContext) -> SourceSummary:
    if isinstance(input_data, dict):
        normalized = input_data["normalized"]
        source_brief = input_data.get("source_brief")
    else:
        normalized = input_data
        source_brief = None
    assert isinstance(normalized, NormalizedBrief)

    if isinstance(source_brief, ReviewPlanSourceBrief):
        topics = list(source_brief.lesson_title_candidates or [])
        if not topics and normalized.known_weaknesses:
            topics.extend(normalized.known_weaknesses)
        risk_notes = []
        if source_brief.missing_fields:
            risk_notes.append("结构化课堂材料缺少：" + "、".join(source_brief.missing_fields))
        if source_brief.confidence < 0.7:
            risk_notes.append("结构化课堂材料置信度偏低，后续计划需要保留 assumptions/warnings。")
        for warning in risk_notes:
            context.add_warning("source_confidence", warning, "medium")
        return SourceSummary(
            source_type="structured_source_brief",
            confirmed_topics=topics,
            assumed_topics=[] if topics else ["根据结构化课堂材料低置信度推断主题"],
            evidence_map=[item.model_dump() for item in source_brief.evidence_map],
            risk_notes=risk_notes,
            confidence=float(source_brief.confidence or 0.0),
            source_brief=source_brief,
        )

    text = "\n".join(normalized.materials).strip()
    confirmed_topics: list[str] = []
    if text:
        for marker in ("本节课主题：", "主题：", "topic:"):
            if marker in text:
                confirmed_topics.append(text.split(marker, 1)[1].splitlines()[0].strip())
                break
    if not confirmed_topics and normalized.known_weaknesses:
        confirmed_topics.extend(normalized.known_weaknesses)

    risk_notes = []
    if not text:
        risk_notes.append("没有课堂材料，无法做证据映射。")
    if normalized.confidence < 0.7:
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


source_analyzer_node: WorkflowNode[dict[str, object] | NormalizedBrief, SourceSummary] = WorkflowNode(
    name="source_analyzer",
    run=_run,
    output_serializer=_source_summary_trace_payload,
)
