from __future__ import annotations

from typing import Any

from .schemas import QualityReview
from .state import WorkflowContext


def apply_revision_policy(plan: dict[str, Any], quality: QualityReview, context: WorkflowContext) -> dict[str, Any]:
    """Phase-1 revision boundary.

    The current production generator is still a compatibility node. Instead of
    silently rewriting the plan deterministically, we attach review metadata and
    let the next implementation step replace this with an LLM revision node.
    """

    if quality.must_revise:
        context.add_warning(
            "quality_revision_required",
            "质量门禁建议 revision；Phase 1 已记录问题并返回当前最优结果。",
            "high",
        )
    return plan
