from __future__ import annotations

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, ReviewPlanInput
from review_plan_workflow.state import WorkflowContext


def _subject_key(value: str) -> str:
    lowered = (value or "").strip().lower()
    if any(token in lowered for token in ("physics", "物理")):
        return "physics"
    if any(token in lowered for token in ("ielts", "雅思", "reading", "listening", "speaking", "writing")):
        return "ielts"
    if any(token in lowered for token in ("math", "数学", "algebra", "geometry")):
        return "math"
    return "unknown"


def _run(input_data: ReviewPlanInput, context: WorkflowContext) -> NormalizedBrief:
    missing_info: list[str] = []
    if not input_data.summary_text.strip():
        missing_info.append("summary_text")
    if not input_data.subject.strip():
        missing_info.append("subject")
    if not input_data.topic.strip():
        missing_info.append("topic")
    if not input_data.lesson_date.strip():
        missing_info.append("lesson_date")

    subject = _subject_key(input_data.subject)
    confidence = max(0.25, 1.0 - len(missing_info) * 0.15)
    if subject == "unknown":
        confidence = min(confidence, 0.55)

    context.subject = subject
    if missing_info:
        context.add_warning("missing_input", f"输入缺少字段：{', '.join(missing_info)}", "medium")

    materials = [input_data.summary_text.strip()] if input_data.summary_text.strip() else []
    known_weaknesses = [input_data.weak_points.strip()] if input_data.weak_points.strip() else []
    return NormalizedBrief(
        subject=subject,  # type: ignore[arg-type]
        known_weaknesses=known_weaknesses,
        materials=materials,
        output_language=input_data.output_language,
        timeframe={"startDate": input_data.lesson_date or None, "endDate": None, "totalDays": 30},
        missing_info=missing_info,
        assumptions=[],
        confidence=confidence,
    )


intake_normalizer_node: WorkflowNode[ReviewPlanInput, NormalizedBrief] = WorkflowNode(
    name="intake_normalizer",
    run=_run,
)
