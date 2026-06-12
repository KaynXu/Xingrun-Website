from __future__ import annotations

from typing import Any

from .schemas import QualityReview
from .state import WorkflowContext


def apply_revision_policy(plan: dict[str, Any], quality: QualityReview, context: WorkflowContext) -> dict[str, Any]:
    """Phase-1 revision boundary.

    The workflow now owns plan generation, but revision still needs a dedicated
    LLM node. Until then, keep quality findings visible without silently
    rewriting student-facing plans deterministically.
    """

    if quality.must_revise:
        context.add_warning(
            "quality_revision_required",
            "质量门禁建议 revision；Phase 1 已记录问题并返回当前最优结果。",
            "high",
        )
    return plan
