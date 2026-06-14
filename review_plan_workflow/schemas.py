from __future__ import annotations

from typing import Any, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SubjectKey = Literal["math", "physics", "ielts", "unknown"]


class ReviewPlanInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary_text: str
    subject: str = ""
    grade: str = ""
    topic: str = ""
    weak_points: str = ""
    lesson_date: str = ""
    output_language: str = "zh-CN"


class NormalizedBrief(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: SubjectKey = "unknown"
    course_system: str = "unknown"
    exam_board: Optional[str] = None
    student_level: Optional[str] = None
    target: Optional[str] = None
    timeframe: dict[str, Any] = Field(default_factory=dict)
    availability: dict[str, Any] = Field(default_factory=dict)
    known_weaknesses: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    student_preferences: list[str] = Field(default_factory=list)
    output_language: str = "zh-CN"
    missing_info: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class SubjectRoute(BaseModel):
    selected_subject: SubjectKey = "unknown"
    subject_pack_path: Optional[str] = None
    reason: str = ""
    requires_special_handling: bool = False
    special_handling_notes: list[str] = Field(default_factory=list)


class SourceSummary(BaseModel):
    source_type: str = "user_input"
    confirmed_topics: list[str] = Field(default_factory=list)
    assumed_topics: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)
    evidence_map: list[dict[str, Any]] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class ScopePlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    planning_mode: str = "single_lesson_spaced_review"
    review_days: list[int] = Field(default_factory=lambda: [1, 2, 7, 14, 30])
    module_sequence: list[str] = Field(default_factory=list)
    review_loop: list[str] = Field(default_factory=list)
    scope_warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class TimeAllocation(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_days: int = 30
    review_schedule: list[dict[str, Any]] = Field(default_factory=list)
    daily_workload_minutes: int = 30
    buffer_strategy: str = ""
    workload_warnings: list[str] = Field(default_factory=list)


class TaskBlueprint(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: SubjectKey = "unknown"
    task_blocks: list[dict[str, Any]] = Field(default_factory=list)
    required_components: list[str] = Field(default_factory=list)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    risk_controls: list[str] = Field(default_factory=list)


class PromptBundle(BaseModel):
    model_config = ConfigDict(extra="allow")

    system_prompt_path: str
    node_prompt_path: str
    subject_pack_path: str
    style_path: str
    rubric_path: str
    prompt_version: str
    prompt: str = Field(default="", exclude=True)
    prompt_preview: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)


class QualityIssue(BaseModel):
    severity: Literal["low", "medium", "high"] = "medium"
    category: str = "completeness"
    description: str
    suggested_fix: str = ""


class QualityReview(BaseModel):
    score: int = 0
    passed: bool = False
    issues: list[QualityIssue] = Field(default_factory=list)
    must_revise: bool = False
    revision_instructions: list[str] = Field(default_factory=list)


class LessonInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: str = ""
    grade: str = ""
    topic: str = ""
    date: str = ""
    key_categories: list[str] = Field(default_factory=list)


class ReviewPlanDay(BaseModel):
    model_config = ConfigDict(extra="allow")

    day: int
    label: str = ""
    time: str = ""
    type: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    choices: list[dict[str, Any]] = Field(default_factory=list)
    self_test_phrase: str = ""

    @field_validator("day")
    @classmethod
    def validate_review_day(cls, value: int) -> int:
        if value not in {1, 2, 7, 14, 30}:
            raise ValueError("single lesson review day must be one of 1, 2, 7, 14, 30")
        return value


class FinalReviewPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    lesson_info: LessonInfo = Field(default_factory=LessonInfo)
    days: list[ReviewPlanDay]
    weak_points_summary: str = ""
    full_review_topics: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    final_reminder_lines: list[str] = Field(default_factory=list)
    knowledge_sections: dict[str, Any] = Field(default_factory=dict)

    @field_validator("days")
    @classmethod
    def validate_days(cls, value: list[ReviewPlanDay]) -> list[ReviewPlanDay]:
        if not value:
            raise ValueError("review plan must include review days")
        return value


def validate_final_review_plan(plan: dict) -> Tuple[Optional[FinalReviewPlan], list[str]]:
    try:
        return FinalReviewPlan.model_validate(plan), []
    except ValidationError as exc:
        return None, [error.get("msg", str(error)) for error in exc.errors()]
