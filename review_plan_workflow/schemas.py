from __future__ import annotations

import copy
from typing import Any, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


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
    title: str = ""
    theme: str = ""
    goal: str = ""
    focus: str = ""
    time: str = ""
    time_minutes: Optional[int] = None
    type: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    blanks: list[dict[str, Any]] = Field(default_factory=list)
    choices: list[dict[str, Any]] = Field(default_factory=list)
    active_recall: Optional[Any] = None
    completion_standard: str = ""
    self_test_phrase: str = ""

    @field_validator("day")
    @classmethod
    def validate_review_day(cls, value: int) -> int:
        if value not in {1, 2, 7, 14, 30}:
            raise ValueError("single lesson review day must be one of 1, 2, 7, 14, 30")
        return value

    @model_validator(mode="after")
    def validate_printable_content(self) -> "ReviewPlanDay":
        if any((self.steps, self.items, self.blanks, self.choices)):
            return self
        if any(
            str(value or "").strip()
            for value in (
                self.self_test_phrase,
                self.goal,
                self.focus,
                self.theme,
                self.title,
                self.completion_standard,
            )
        ):
            return self
        raise ValueError("review day must include printable task content")


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
    normalized = normalize_final_review_plan(plan)
    try:
        return FinalReviewPlan.model_validate(normalized), []
    except ValidationError as exc:
        return None, [error.get("msg", str(error)) for error in exc.errors()]


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_choice(choice: dict[str, Any]) -> dict[str, Any]:
    question = _clean_text(choice.get("question") or choice.get("stem"))
    options = [str(option).strip() for option in choice.get("options", []) if str(option or "").strip()]
    normalized: dict[str, Any] = {}
    if question:
        normalized["question"] = question
    if options:
        normalized["options"] = options
    answer = _clean_text(choice.get("answer"))
    if answer:
        normalized["answer"] = answer
    analysis = _clean_text(choice.get("analysis"))
    if analysis:
        normalized["analysis"] = analysis
    return normalized


def _normalize_blank(blank: Any) -> dict[str, Any]:
    if isinstance(blank, dict):
        return {
            "text": _clean_text(blank.get("text")),
            "answer": _clean_text(blank.get("answer")),
        }
    if isinstance(blank, (list, tuple)) and blank:
        text = _clean_text(blank[0])
        answer = _clean_text(blank[1]) if len(blank) > 1 else ""
        return {"text": text, "answer": answer}
    text = _clean_text(blank)
    return {"text": text, "answer": ""}


def _append_unique_body(items: list[dict[str, Any]], text: str) -> None:
    clean = _clean_text(text)
    if not clean:
        return
    for item in items:
        if item.get("type") == "body" and _clean_text(item.get("text")) == clean:
            return
    items.append({"type": "body", "text": clean})


def _normalize_day(day: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(day)
    day_number = int(normalized.get("day") or 0) or 1

    if not _clean_text(normalized.get("label")):
        normalized["label"] = (
            _clean_text(normalized.get("title"))
            or _clean_text(normalized.get("theme"))
            or f"第{day_number}天复习"
        )
    if not _clean_text(normalized.get("time")):
        time_minutes = normalized.get("time_minutes")
        if isinstance(time_minutes, int) and time_minutes > 0:
            normalized["time"] = f"{time_minutes}分钟"

    items = [copy.deepcopy(item) for item in normalized.get("items", []) if isinstance(item, dict)]
    _append_unique_body(items, normalized.get("goal", ""))
    _append_unique_body(items, normalized.get("focus", ""))

    active_recall = normalized.get("active_recall")
    if isinstance(active_recall, dict):
        _append_unique_body(items, active_recall.get("instructions", ""))
        if not _clean_text(normalized.get("self_test_phrase")):
            normalized["self_test_phrase"] = (
                _clean_text(active_recall.get("expected"))
                or _clean_text(active_recall.get("instructions"))
            )
    elif isinstance(active_recall, str):
        _append_unique_body(items, active_recall)
        if not _clean_text(normalized.get("self_test_phrase")):
            normalized["self_test_phrase"] = _clean_text(active_recall)

    normalized_blanks: list[dict[str, Any]] = []
    for blank in normalized.get("blanks", []) if isinstance(normalized.get("blanks"), list) else []:
        normalized_blank = _normalize_blank(blank)
        if normalized_blank.get("text"):
            normalized_blanks.append(normalized_blank)
            items.append(
                {
                    "type": "fill",
                    "text": normalized_blank["text"],
                    "answer": normalized_blank.get("answer", ""),
                }
            )
    normalized["blanks"] = normalized_blanks
    normalized["items"] = items

    normalized_choices: list[dict[str, Any]] = []
    for choice in normalized.get("choices", []) if isinstance(normalized.get("choices"), list) else []:
        if not isinstance(choice, dict):
            continue
        normalized_choice = _normalize_choice(choice)
        if normalized_choice.get("question") and normalized_choice.get("options"):
            normalized_choices.append(normalized_choice)
    normalized["choices"] = normalized_choices

    if not _clean_text(normalized.get("self_test_phrase")):
        normalized["self_test_phrase"] = (
            _clean_text(normalized.get("completion_standard"))
            or _clean_text(normalized.get("title"))
            or _clean_text(normalized.get("theme"))
        )
    return normalized


def normalize_final_review_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(plan or {})
    lesson_info = normalized.setdefault("lesson_info", {})
    if not isinstance(lesson_info, dict):
        lesson_info = {}
        normalized["lesson_info"] = lesson_info

    if not _clean_text(normalized.get("weak_points_summary")):
        weak_points = lesson_info.get("weak_points")
        if isinstance(weak_points, list):
            normalized["weak_points_summary"] = "；".join(
                text for text in (_clean_text(item) for item in weak_points) if text
            )
        else:
            normalized["weak_points_summary"] = _clean_text(weak_points)

    full_review_topics = normalized.get("full_review_topics")
    if not isinstance(full_review_topics, list):
        full_review_topics = []
    key_categories = lesson_info.get("key_categories")
    if isinstance(key_categories, list):
        for category in key_categories:
            text = _clean_text(category)
            if text and text not in full_review_topics:
                full_review_topics.append(text)
    normalized["full_review_topics"] = full_review_topics

    days = normalized.get("days")
    if not isinstance(days, list):
        normalized["days"] = []
        return normalized

    normalized["days"] = [_normalize_day(day) for day in days if isinstance(day, dict)]
    return normalized
