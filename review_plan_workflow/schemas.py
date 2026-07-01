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
    schedule_mode: str = "standard"
    review_days: list[int] = Field(default_factory=lambda: [1, 2, 7, 14, 30])
    daily_count: Optional[int] = None
    user_requirements: str = ""
    output_language: str = "zh-CN"

    @field_validator("review_days")
    @classmethod
    def validate_review_days(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("review_days must not be empty")
        for day in value:
            if isinstance(day, bool) or not isinstance(day, int) or day <= 0:
                raise ValueError("review_days must contain positive integers")
        return value


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


class AgenticDayStrategy(BaseModel):
    model_config = ConfigDict(extra="allow")

    day: int
    objective: str = ""
    retrieval_focus: list[str] = Field(default_factory=list)
    question_design: list[str] = Field(default_factory=list)
    review_loop: list[str] = Field(default_factory=list)
    risk_controls: list[str] = Field(default_factory=list)

    @field_validator("day")
    @classmethod
    def validate_review_day(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("agentic day strategy must target a positive day integer")
        return value


class AgenticPlanBlueprint(BaseModel):
    model_config = ConfigDict(extra="allow")

    strategy_summary: str = ""
    student_diagnosis: list[str] = Field(default_factory=list)
    knowledge_map: list[dict[str, Any]] = Field(default_factory=list)
    day_strategies: list[AgenticDayStrategy] = Field(default_factory=list)
    writer_instructions: list[str] = Field(default_factory=list)
    quality_risks: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0


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
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("single lesson review day must be a positive integer")
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
    if isinstance(value, (dict, list, tuple, set)):
        return ""
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
            "text": _clean_text(blank.get("text") or blank.get("stem") or blank.get("question")),
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


def _append_unique_blank(blanks: list[dict[str, Any]], blank: dict[str, Any]) -> None:
    text = _clean_text(blank.get("text"))
    if not text:
        return
    answer = _clean_text(blank.get("answer"))
    for existing in blanks:
        if _clean_text(existing.get("text")) == text:
            return
    blanks.append({"text": text, "answer": answer})


def _append_unique_choice(choices: list[dict[str, Any]], choice: dict[str, Any]) -> None:
    normalized_choice = _normalize_choice(choice)
    if not normalized_choice.get("question") or not normalized_choice.get("options"):
        return
    question = _clean_text(normalized_choice.get("question"))
    for existing in choices:
        if _clean_text(existing.get("question")) == question:
            return
    choices.append(normalized_choice)


def _normalize_component_payload(day: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    blanks: list[dict[str, Any]] = []
    choices: list[dict[str, Any]] = []
    body_items: list[str] = []
    quotes: list[str] = []
    components = day.get("components")
    if not isinstance(components, list):
        return blanks, choices, body_items, quotes

    for component in components:
        if not isinstance(component, dict):
            continue
        component_type = _clean_text(component.get("type")).lower()
        quote = _clean_text(component.get("quote"))
        if quote and quote not in quotes:
            quotes.append(quote)
        title = _clean_text(component.get("title"))
        for item in component.get("items", []) if isinstance(component.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            if component_type == "choices_card":
                _append_unique_choice(choices, item)
                continue
            stem = _clean_text(item.get("text") or item.get("stem") or item.get("question"))
            answer = _clean_text(item.get("answer"))
            if not stem:
                continue
            if component_type in {"active_recall_card", "teacher_oral_card"}:
                body_items.append(stem if not title else f"{title}：{stem}")
                if "______" in stem:
                    _append_unique_blank(blanks, {"text": stem, "answer": answer})
            elif component_type == "blanks_card" or "______" in stem:
                _append_unique_blank(blanks, {"text": stem, "answer": answer})
            else:
                body_items.append(stem if not title else f"{title}：{stem}")
    return blanks, choices, body_items, quotes


def _item_text(value: dict[str, Any]) -> str:
    return _clean_text(
        value.get("text")
        or value.get("stem")
        or value.get("question")
        or value.get("prompt")
        or value.get("task")
        or value.get("front")
    )


def _normalize_task_payload(value: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    blanks: list[dict[str, Any]] = []
    choices: list[dict[str, Any]] = []
    body_items: list[str] = []

    def collect(item: Any, parent_key: str = "") -> None:
        key = parent_key.lower()
        if isinstance(item, dict):
            if key in {"blanks", "fillinblanks", "blanks_spiral"}:
                normalized_blank = _normalize_blank(item)
                if normalized_blank.get("text"):
                    _append_unique_blank(blanks, normalized_blank)
            elif isinstance(item.get("options"), list):
                _append_unique_choice(choices, item)
            else:
                text = _item_text(item)
                if text:
                    if "______" in text and any(field in item for field in ("answer", "reference_answer", "answer_hint")):
                        _append_unique_blank(blanks, {"text": text, "answer": item.get("answer") or item.get("reference_answer") or item.get("answer_hint")})
                    else:
                        _append_unique_body_from_task(text)

            for nested_key, nested_value in item.items():
                normalized_key = str(nested_key)
                if normalized_key in {"options"}:
                    continue
                if normalized_key in {"blanks", "fillInBlanks", "blanks_spiral"} and isinstance(nested_value, list):
                    for nested_item in nested_value:
                        collect(nested_item, normalized_key)
                    continue
                if normalized_key in {"choices", "multipleChoice"} and isinstance(nested_value, list):
                    for nested_item in nested_value:
                        collect(nested_item, normalized_key)
                    continue
                if normalized_key in {"items", "cards", "questions", "oral_cards"} and isinstance(nested_value, list):
                    for nested_item in nested_value:
                        collect(nested_item, normalized_key)
                    continue
                if isinstance(nested_value, (dict, list)):
                    collect(nested_value, normalized_key)
        elif isinstance(item, list):
            for nested_item in item:
                collect(nested_item, parent_key)
        else:
            text = _clean_text(item)
            if text and key in {"blanks", "fillinblanks", "blanks_spiral"}:
                _append_unique_blank(blanks, {"text": text, "answer": ""})
            elif text:
                _append_unique_body_from_task(text)

    def _append_unique_body_from_task(text: str) -> None:
        clean = _clean_text(text)
        if clean and clean not in body_items:
            body_items.append(clean)

    collect(value)
    return blanks, choices, body_items


def _normalize_day(day: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(day)
    try:
        day_number = int(normalized.get("day") or normalized.get("day_number") or 0) or 1
    except (TypeError, ValueError):
        day_number = 1
    normalized["day"] = day_number

    if not _clean_text(normalized.get("goal")):
        normalized["goal"] = _clean_text(
            normalized.get("reviewGoal")
            or normalized.get("review_goal")
            or normalized.get("objective")
        )
    if not _clean_text(normalized.get("focus")):
        normalized["focus"] = _clean_text(normalized.get("reviewFocus") or normalized.get("review_focus"))
    if not _clean_text(normalized.get("completion_standard")):
        normalized["completion_standard"] = _clean_text(
            normalized.get("completionCriteria")
            or normalized.get("completion_criteria")
        )
    if "active_recall" not in normalized and isinstance(normalized.get("activeRecall"), (dict, str)):
        normalized["active_recall"] = normalized.get("activeRecall")

    day_task_card = normalized.get("day_task_card")
    if isinstance(day_task_card, dict):
        if not _clean_text(normalized.get("goal")):
            normalized["goal"] = _clean_text(day_task_card.get("review_goal") or day_task_card.get("goal"))
        if not _clean_text(normalized.get("focus")):
            normalized["focus"] = _clean_text(day_task_card.get("focus"))
        if not _clean_text(normalized.get("title")):
            normalized["title"] = _clean_text(day_task_card.get("title"))
        if not normalized.get("time_minutes") and isinstance(day_task_card.get("target_minutes"), int):
            normalized["time_minutes"] = day_task_card.get("target_minutes")

    if not _clean_text(normalized.get("label")):
        normalized["label"] = (
            _clean_text(normalized.get("title"))
            or _clean_text(normalized.get("theme"))
            or f"第{day_number}天复习"
        )
    if not _clean_text(normalized.get("time")):
        estimate_text = _clean_text(normalized.get("time_estimate"))
        if estimate_text:
            normalized["time"] = estimate_text
        time_minutes = normalized.get("time_minutes")
        if not normalized.get("time") and isinstance(time_minutes, int) and time_minutes > 0:
            normalized["time"] = f"{time_minutes}分钟"

    component_blanks, component_choices, component_body_items, component_quotes = _normalize_component_payload(normalized)
    task_blanks, task_choices, task_body_items = _normalize_task_payload(normalized.get("tasks"))
    items = [copy.deepcopy(item) for item in normalized.get("items", []) if isinstance(item, dict)]
    _append_unique_body(items, normalized.get("goal", ""))
    _append_unique_body(items, normalized.get("focus", ""))
    for text in component_body_items:
        _append_unique_body(items, text)
    for text in task_body_items:
        _append_unique_body(items, text)

    active_recall_blanks: list[dict[str, Any]] = []
    active_recall = normalized.get("active_recall")
    if isinstance(active_recall, dict):
        _append_unique_body(items, active_recall.get("instructions", ""))
        content = active_recall.get("content")
        answers = active_recall.get("answers") if isinstance(active_recall.get("answers"), list) else []
        for index, content_item in enumerate(content if isinstance(content, list) else []):
            answer = _clean_text(answers[index]) if index < len(answers) else ""
            if isinstance(content_item, dict):
                text_parts = [
                    _clean_text(content_item.get("stem")),
                    _clean_text(content_item.get("question")),
                    _clean_text(content_item.get("answerHint") or content_item.get("answer_hint")),
                ]
                text = " ".join(part for part in text_parts if part)
            else:
                text = _clean_text(content_item)
            if text:
                _append_unique_body(items, text)
                if "______" in text:
                    _append_unique_blank(active_recall_blanks, {"text": text, "answer": answer})
        for item in active_recall.get("items", []) if isinstance(active_recall.get("items"), list) else []:
            if isinstance(item, dict):
                text = _clean_text(item.get("text") or item.get("stem") or item.get("question"))
            else:
                text = _clean_text(item)
            if text:
                _append_unique_body(items, text)
                if "______" in text:
                    _append_unique_blank(active_recall_blanks, {"text": text, "answer": ""})
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
    raw_blanks: list[Any] = []
    if isinstance(normalized.get("blanks"), list):
        raw_blanks.extend(normalized.get("blanks", []))
    if isinstance(normalized.get("fillInBlanks"), list):
        raw_blanks.extend(normalized.get("fillInBlanks", []))
    mini_test = normalized.get("mini_test")
    if isinstance(mini_test, dict) and isinstance(mini_test.get("blanks"), list):
        raw_blanks.extend(mini_test.get("blanks", []))
    for blank in raw_blanks:
        normalized_blank = _normalize_blank(blank)
        if normalized_blank.get("text"):
            _append_unique_blank(normalized_blanks, normalized_blank)
    for blank in component_blanks:
        _append_unique_blank(normalized_blanks, blank)
    for blank in task_blanks:
        _append_unique_blank(normalized_blanks, blank)
    for blank in active_recall_blanks:
        _append_unique_blank(normalized_blanks, blank)
    for normalized_blank in normalized_blanks:
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
    raw_choices: list[Any] = []
    if isinstance(normalized.get("choices"), list):
        raw_choices.extend(normalized.get("choices", []))
    if isinstance(normalized.get("multipleChoice"), list):
        raw_choices.extend(normalized.get("multipleChoice", []))
    if isinstance(mini_test, dict) and isinstance(mini_test.get("choices"), list):
        raw_choices.extend(mini_test.get("choices", []))
    for choice in raw_choices:
        if not isinstance(choice, dict):
            continue
        _append_unique_choice(normalized_choices, choice)
    for choice in component_choices:
        _append_unique_choice(normalized_choices, choice)
    for choice in task_choices:
        _append_unique_choice(normalized_choices, choice)
    normalized["choices"] = normalized_choices

    if component_quotes:
        day_quotes = normalized.get("quotes")
        if not isinstance(day_quotes, list):
            day_quotes = []
        for quote in component_quotes:
            if quote not in day_quotes:
                day_quotes.append(quote)
        normalized["quotes"] = day_quotes

    for oral_card in normalized.get("oral_cards", []) if isinstance(normalized.get("oral_cards"), list) else []:
        if not isinstance(oral_card, dict):
            continue
        text = " ".join(
            part for part in (
                _clean_text(oral_card.get("stem")),
                _clean_text(oral_card.get("question")),
            )
            if part
        )
        _append_unique_body(items, text)
    if isinstance(mini_test, dict):
        short_question = mini_test.get("short_question")
        if isinstance(short_question, dict):
            text = " ".join(
                part for part in (
                    _clean_text(short_question.get("stem")),
                    _clean_text(short_question.get("question")),
                    _clean_text(short_question.get("reference_answer")),
                )
                if part
            )
            _append_unique_body(items, text)
    normalized["items"] = items

    if not _clean_text(normalized.get("self_test_phrase")):
        normalized["self_test_phrase"] = (
            _clean_text(normalized.get("completion_standard"))
            or _clean_text(normalized.get("title"))
            or _clean_text(normalized.get("theme"))
        )
    return normalized


def _has_final_plan_fields(value: dict[str, Any]) -> bool:
    return any(key in value for key in ("lesson_info", "days", "full_review_topics", "quotes"))


def _find_wrapped_final_plan(value: dict[str, Any], depth: int = 0) -> dict[str, Any] | None:
    if depth >= 3:
        return None
    for key in ("reviewPlan", "plan", "result", "data", "output", "content", "response"):
        candidate = value.get(key)
        if not isinstance(candidate, dict):
            continue
        if _has_final_plan_fields(candidate):
            return candidate
        nested = _find_wrapped_final_plan(candidate, depth + 1)
        if nested is not None:
            return nested
    return None


def normalize_final_review_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(plan or {})
    wrapped_plan = _find_wrapped_final_plan(normalized)
    if isinstance(wrapped_plan, dict):
        for source_key, target_key in (
            ("subject", "subject"),
            ("grade", "grade"),
            ("topic", "topic"),
            ("lessonDate", "lesson_date"),
            ("generatedDate", "date_generated"),
        ):
            if not _clean_text(normalized.get(target_key)):
                normalized[target_key] = _clean_text(wrapped_plan.get(source_key))
        wrapped_lesson_info = wrapped_plan.get("lesson_info")
        if isinstance(wrapped_lesson_info, dict):
            lesson_info = normalized.get("lesson_info")
            if not isinstance(lesson_info, dict):
                lesson_info = {}
                normalized["lesson_info"] = lesson_info
            for key in ("subject", "topic", "grade", "date", "key_categories", "weak_points"):
                if lesson_info.get(key) in (None, "", [], {}):
                    wrapped_value = wrapped_lesson_info.get(key)
                    if wrapped_value not in (None, "", [], {}):
                        lesson_info[key] = wrapped_value
        if not isinstance(normalized.get("days"), list) or not normalized.get("days"):
            wrapped_days = wrapped_plan.get("days")
            if isinstance(wrapped_days, list):
                normalized["days"] = wrapped_days
        for key in ("full_review_topics", "quotes", "final_reminder_lines", "knowledge_sections"):
            if key not in normalized or normalized.get(key) in (None, "", [], {}):
                wrapped_value = wrapped_plan.get(key)
                if wrapped_value not in (None, "", [], {}):
                    normalized[key] = wrapped_value

    lesson_info = normalized.setdefault("lesson_info", {})
    if not isinstance(lesson_info, dict):
        lesson_info = {}
        normalized["lesson_info"] = lesson_info

    if not _clean_text(lesson_info.get("subject")):
        lesson_info["subject"] = _clean_text(normalized.get("subject"))
    if not _clean_text(lesson_info.get("topic")):
        lesson_info["topic"] = _clean_text(normalized.get("topic") or normalized.get("lesson_topic"))

    grade_value = lesson_info.get("grade")
    if grade_value in (None, ""):
        grade_value = normalized.get("grade")
    lesson_info["grade"] = _clean_text(grade_value)

    date_value = lesson_info.get("date")
    if not _clean_text(date_value):
        date_value = normalized.get("lesson_date") or normalized.get("generate_date") or normalized.get("date_generated")
    lesson_info["date"] = _clean_text(date_value)

    key_categories = lesson_info.get("key_categories")
    if not isinstance(key_categories, list):
        key_categories = []
    homepage = normalized.get("homepage")
    if isinstance(homepage, dict):
        coverage_box = homepage.get("full_coverage_box")
        if isinstance(coverage_box, dict):
            for field in ("topics", "methods", "error_patterns", "question_types"):
                for category in coverage_box.get(field, []):
                    text = _clean_text(category)
                    if text and text not in key_categories:
                        key_categories.append(text)
    lesson_info["key_categories"] = key_categories

    if not _clean_text(normalized.get("weak_points_summary")):
        weak_points = lesson_info.get("weak_points")
        if isinstance(weak_points, list):
            normalized["weak_points_summary"] = "；".join(
                text for text in (_clean_text(item) for item in weak_points) if text
            )
        else:
            normalized["weak_points_summary"] = _clean_text(weak_points)
    if not _clean_text(normalized.get("weak_points_summary")) and isinstance(normalized.get("home_usage_box"), dict):
        normalized["weak_points_summary"] = _clean_text(normalized["home_usage_box"].get("content"))

    full_review_topics = normalized.get("full_review_topics")
    if not isinstance(full_review_topics, list):
        full_review_topics = []
    topic_text = _clean_text(lesson_info.get("topic"))
    if topic_text and not full_review_topics and not key_categories:
        full_review_topics.append(topic_text)
    for category in lesson_info.get("key_categories", []):
        text = _clean_text(category)
        if text and text not in full_review_topics:
            full_review_topics.append(text)
    normalized["full_review_topics"] = full_review_topics

    quotes = normalized.get("quotes")
    if not isinstance(quotes, list):
        quotes = []
    if isinstance(homepage, dict):
        golden_quote = _clean_text(homepage.get("golden_quote_box"))
        if golden_quote and golden_quote not in quotes:
            quotes.append(golden_quote)
        home_usage = _clean_text(homepage.get("home_usage_box"))
        if home_usage and not _dedupe_clean_list(normalized.get("final_reminder_lines")):
            normalized["final_reminder_lines"] = [home_usage]
    if isinstance(normalized.get("home_usage_box"), dict):
        home_usage = _clean_text(normalized["home_usage_box"].get("content"))
        if home_usage and not _dedupe_clean_list(normalized.get("final_reminder_lines")):
            normalized["final_reminder_lines"] = [home_usage]
    normalized["quotes"] = quotes

    knowledge_sections = normalized.get("knowledge_sections")
    if not isinstance(knowledge_sections, dict):
        knowledge_sections = {}
    if isinstance(homepage, dict) and isinstance(homepage.get("core_formula_card"), dict):
        knowledge_sections.setdefault("formula_card", homepage["core_formula_card"])
    normalized["knowledge_sections"] = knowledge_sections

    days = normalized.get("days")
    if not isinstance(days, list):
        normalized["days"] = []
        return normalized

    normalized["days"] = [_normalize_day(day) for day in days if isinstance(day, dict)]
    return normalized


def _dedupe_clean_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    lines: list[str] = []
    for value in values:
        text = _clean_text(value)
        if text and text not in lines:
            lines.append(text)
    return lines
