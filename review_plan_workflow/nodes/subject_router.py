from __future__ import annotations

from pathlib import Path

from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.schemas import NormalizedBrief, SubjectRoute
from review_plan_workflow.state import WorkflowContext


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"


def _run(input_data: NormalizedBrief, context: WorkflowContext) -> SubjectRoute:
    subject = input_data.subject
    pack_path = PROMPT_ROOT / "subjects" / f"{subject}.yaml"
    if subject == "unknown" or not pack_path.exists():
        context.add_warning("unknown_subject", "无法确定学科包，已使用公共规则兜底。", "high")
        return SubjectRoute(
            selected_subject="unknown",
            subject_pack_path=str(PROMPT_ROOT / "subjects" / "common.yaml"),
            reason="subject is missing or not mapped",
            requires_special_handling=True,
            special_handling_notes=["使用 common.yaml，不套用数学/物理/雅思专属检查。"],
        )
    return SubjectRoute(
        selected_subject=subject,
        subject_pack_path=str(pack_path),
        reason=f"matched {subject} subject pack",
        requires_special_handling=subject in {"physics", "ielts"},
        special_handling_notes=[],
    )


subject_router_node: WorkflowNode[NormalizedBrief, SubjectRoute] = WorkflowNode(
    name="subject_router",
    run=_run,
)
