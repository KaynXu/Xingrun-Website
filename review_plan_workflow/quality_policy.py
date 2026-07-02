from __future__ import annotations

from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief


ALWAYS_SOFT_CATEGORIES_AFTER_REVISION = {"workload_sanity"}
SOFT_EVIDENCE_CATEGORIES_AFTER_REVISION = {"subject_fit", "factuality", "style_consistency"}
SOFT_EVIDENCE_MARKERS = (
    "source_brief",
    "缺失 topic",
    "缺少 topic",
    "缺失主题",
    "缺少主题",
    "knowledge_points",
    "lesson_title_candidates_count",
    "证据边界",
    "推测内容",
    "推测主题",
    "低置信",
    "低证据",
    "素材不足",
    "材料不足",
    "课堂材料不足",
    "无法核验",
    "待确认",
    "evidence boundary",
    "inferred topic",
    "assumed topic",
)
HARD_EVIDENCE_MARKERS = (
    "答案错误",
    "答案不正确",
    "计算错误",
    "数学错误",
    "事实错误",
    "选项错误",
    "schema",
    "review days",
    "review_days",
    "没有可渲染",
    "空答案",
    "无法打印",
    "pdf",
    "渲染",
    "老师原话",
    "teacher quote",
    "teacher_emphasis",
)


def _has_high_issue(quality: QualityReview) -> bool:
    return any(issue.severity == "high" for issue in quality.issues)


def _has_repairable_question_issue(quality: QualityReview) -> bool:
    return any(
        issue.severity == "high"
        and issue.category in {"question_quality", "factuality", "pdf_safety"}
        for issue in quality.issues
    )


def _issue_text(issue: object) -> str:
    return " ".join(
        str(getattr(issue, key, "") or "")
        for key in ("description", "suggested_fix", "category")
    ).lower()


def is_soft_issue_after_revision(issue: object) -> bool:
    category = str(getattr(issue, "category", "") or "")
    if category in ALWAYS_SOFT_CATEGORIES_AFTER_REVISION:
        return True
    if category not in SOFT_EVIDENCE_CATEGORIES_AFTER_REVISION:
        return False
    text = _issue_text(issue)
    if any(marker.lower() in text for marker in HARD_EVIDENCE_MARKERS):
        return False
    return any(marker.lower() in text for marker in SOFT_EVIDENCE_MARKERS)


def can_soft_pass_after_revision(quality: QualityReview) -> bool:
    issues = quality.issues or []
    if not issues:
        return False
    soft_issues = [issue for issue in issues if is_soft_issue_after_revision(issue)]
    if not soft_issues:
        return False
    hard_high_issues = [issue for issue in issues if issue.severity == "high" and not is_soft_issue_after_revision(issue)]
    return not hard_high_issues


def soften_quality_after_revision(quality: QualityReview) -> QualityReview:
    if not can_soft_pass_after_revision(quality):
        return quality
    issues = [
        issue.model_copy(update={"severity": "medium"})
        if issue.severity == "high" and is_soft_issue_after_revision(issue)
        else issue
        for issue in quality.issues
    ]
    return QualityReview(
        score=max(85, min(100, int(quality.score or 0))),
        passed=True,
        issues=issues,
        must_revise=False,
        revision_instructions=quality.revision_instructions,
    )


def soft_pass_warning_for_quality(quality: QualityReview) -> tuple[str, str]:
    categories = {str(issue.category or "") for issue in quality.issues or [] if is_soft_issue_after_revision(issue)}
    if categories and categories <= {"workload_sanity"}:
        return (
            "quality_workload_soft_pass",
            "复习计划任务量偏重，已完成一次自动修订；剩余 workload 提醒不再阻断文档生成。",
        )
    return (
        "quality_evidence_soft_pass",
        "课堂材料证据较弱，已完成一次自动修订；剩余低证据提醒降级为可交付提示，不再阻断文档生成。",
    )


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
    if can_soft_pass_after_revision(quality):
        return 1
    if _has_repairable_question_issue(quality):
        return 2
    return 1
