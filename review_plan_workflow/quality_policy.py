from __future__ import annotations

from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief


def _has_high_issue(quality: QualityReview) -> bool:
    return any(issue.severity == "high" for issue in quality.issues)


def should_run_llm_quality_review(
    *,
    local_quality: QualityReview,
    source_brief: ReviewPlanSourceBrief | None,
) -> bool:
    if not local_quality.passed or local_quality.must_revise or _has_high_issue(local_quality):
        return True
    if local_quality.score < 92:
        return True
    if source_brief is None:
        return True
    if source_brief.confidence < 0.75:
        return True
    if source_brief.missing_fields:
        return True
    return False


def max_revision_attempts_for_quality(
    *,
    quality: QualityReview,
    source_brief: ReviewPlanSourceBrief | None,
) -> int:
    if quality.passed and not quality.must_revise and not _has_high_issue(quality):
        return 0
    if not quality.revision_instructions and not quality.issues:
        return 0
    return 1
