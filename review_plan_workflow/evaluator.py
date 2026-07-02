from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from review_plan_workflow.schemas import QualityIssue, QualityReview
from review_plan_workflow.validator import ReviewPlanValidationResult


EvaluationCategory = Literal["pedagogy", "source_confidence", "factuality", "workload", "style", "delivery_contract"]

ISSUE_CATEGORY_TO_EVALUATION: dict[str, EvaluationCategory] = {
    "schema": "delivery_contract",
    "schedule": "delivery_contract",
    "constraints": "delivery_contract",
    "answers": "delivery_contract",
    "math_blocks": "delivery_contract",
    "source_coverage": "delivery_contract",
    "renderer": "delivery_contract",
    "pdf_readiness": "delivery_contract",
    "pdf_safety": "delivery_contract",
    "task_actionability": "pedagogy",
    "review_loop": "pedagogy",
    "subject_fit": "source_confidence",
    "question_quality": "factuality",
    "factuality": "factuality",
    "workload_sanity": "workload",
    "style_consistency": "style",
}


class ReviewPlanEvaluationIssue(BaseModel):
    model_config = ConfigDict(extra="allow")

    severity: Literal["low", "medium", "high"] = "medium"
    category: EvaluationCategory
    source: Literal["validator", "local_quality", "llm_reviewer"] = "local_quality"
    description: str
    suggested_fix: str = ""
    target_path: str = ""


class ReviewPlanEvaluationResult(BaseModel):
    score: int = 0
    passed: bool = False
    must_revise: bool = False
    validator_passed: bool = True
    llm_review_used: bool = False
    issues: list[ReviewPlanEvaluationIssue] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)


def evaluation_category_for_issue(category: str) -> EvaluationCategory:
    return ISSUE_CATEGORY_TO_EVALUATION.get(str(category or ""), "pedagogy")


def _issue_from_quality(issue: QualityIssue, *, source: Literal["local_quality", "llm_reviewer"]) -> ReviewPlanEvaluationIssue:
    return ReviewPlanEvaluationIssue(
        severity=issue.severity,
        category=evaluation_category_for_issue(issue.category),
        source=source,
        description=issue.description,
        suggested_fix=issue.suggested_fix,
        target_path=issue.target_path,
    )


def _issue_from_validator(issue: object) -> ReviewPlanEvaluationIssue:
    severity = str(getattr(issue, "severity", "") or "medium")
    if severity not in {"low", "medium", "high"}:
        severity = "medium"
    return ReviewPlanEvaluationIssue(
        severity=severity,  # type: ignore[arg-type]
        category=evaluation_category_for_issue(str(getattr(issue, "category", "") or "")),
        source="validator",
        description=str(getattr(issue, "description", "") or ""),
        target_path=str(getattr(issue, "target_path", "") or ""),
    )


def _dedupe_evaluation_issues(issues: list[ReviewPlanEvaluationIssue]) -> list[ReviewPlanEvaluationIssue]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[ReviewPlanEvaluationIssue] = []
    for issue in issues:
        key = (issue.severity, issue.category, issue.source, issue.description)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def build_review_plan_evaluation(
    *,
    local_quality: QualityReview,
    validator_result: ReviewPlanValidationResult | None = None,
    llm_quality: QualityReview | None = None,
) -> ReviewPlanEvaluationResult:
    issues: list[ReviewPlanEvaluationIssue] = []
    instructions: list[str] = []
    validator_passed = True
    if validator_result is not None:
        validator_passed = validator_result.passed
        issues.extend(_issue_from_validator(issue) for issue in validator_result.issues)

    issues.extend(_issue_from_quality(issue, source="local_quality") for issue in local_quality.issues)
    instructions.extend(str(item) for item in local_quality.revision_instructions if str(item or "").strip())
    if llm_quality is not None:
        issues.extend(_issue_from_quality(issue, source="llm_reviewer") for issue in llm_quality.issues)
        for item in llm_quality.revision_instructions:
            text = str(item or "").strip()
            if text and text not in instructions:
                instructions.append(text)

    issues = _dedupe_evaluation_issues(issues)
    has_high_issue = any(issue.severity == "high" for issue in issues)
    base_score = int(local_quality.score or 0)
    if llm_quality is not None:
        base_score = min(base_score, int(llm_quality.score or 0))
    if validator_result is not None and not validator_result.passed:
        base_score = min(base_score, 60)

    must_revise = bool(
        not validator_passed
        or local_quality.must_revise
        or (llm_quality.must_revise if llm_quality is not None else False)
        or base_score < 85
        or has_high_issue
    )
    passed = bool(validator_passed and local_quality.passed and (llm_quality.passed if llm_quality is not None else True)) and not must_revise
    return ReviewPlanEvaluationResult(
        score=max(0, min(100, base_score)),
        passed=passed,
        must_revise=must_revise,
        validator_passed=validator_passed,
        llm_review_used=llm_quality is not None,
        issues=issues,
        revision_instructions=instructions,
    )
