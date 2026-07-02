from __future__ import annotations

from typing import Any, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class PlanV1Audience(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: str = ""
    grade: str = ""
    student_level: str = ""
    lesson_date: str = ""


class PlanV1KnowledgeItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    title: str
    summary: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    practice_focus: list[str] = Field(default_factory=list)


class PlanV1ScheduleItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    day: int
    label: str = ""
    focus: str
    time_minutes: Optional[int] = None
    actions: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)

    @field_validator("day")
    @classmethod
    def validate_day(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("review_schedule.day must be a positive integer")
        return value

    @model_validator(mode="after")
    def validate_work(self) -> "PlanV1ScheduleItem":
        if not self.actions and not self.outputs:
            raise ValueError("review_schedule item must include actions or outputs")
        return self


class PlanV1PracticeTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    day: int
    task_type: str = "short_answer"
    question: str
    options: list[str] = Field(default_factory=list)
    answer: str
    analysis: str = ""
    knowledge_ids: list[str] = Field(default_factory=list)
    source_segment_ids: list[str] = Field(default_factory=list)

    @field_validator("day")
    @classmethod
    def validate_day(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("practice_tasks.day must be a positive integer")
        return value

    @model_validator(mode="after")
    def validate_answer_and_options(self) -> "PlanV1PracticeTask":
        if not str(self.answer or "").strip():
            raise ValueError("practice task must include answer")
        if self.task_type in {"choice", "multiple_choice"} or self.options:
            if len([option for option in self.options if str(option or "").strip()]) < 4:
                raise ValueError("choice practice task must include at least 4 options")
            if str(self.answer or "").strip()[:1].upper() not in {"A", "B", "C", "D"}:
                raise ValueError("choice practice task answer must be A/B/C/D")
        return self


class PlanV1SelfCheckQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    day: int
    question: str
    answer: str
    check_type: str = "self_check"

    @field_validator("day")
    @classmethod
    def validate_day(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("self_check_questions.day must be a positive integer")
        return value

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        if not str(value or "").strip():
            raise ValueError("self-check question must include answer")
        return value


class PlanV1MathBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    latex: str
    display: bool = False


class PlanV1TeacherCheckpoint(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    text: str
    source_segment_ids: list[str] = Field(default_factory=list)


class PlanV1SourceCoverage(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_segment_id: str
    covered_by: list[str] = Field(default_factory=list)


class LessonReviewPlanV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["lesson_review_plan_v1"]
    document_title: str
    audience: PlanV1Audience = Field(default_factory=PlanV1Audience)
    lesson_summary: str = ""
    knowledge_map: list[PlanV1KnowledgeItem] = Field(default_factory=list)
    review_schedule: list[PlanV1ScheduleItem]
    practice_tasks: list[PlanV1PracticeTask] = Field(default_factory=list)
    self_check_questions: list[PlanV1SelfCheckQuestion] = Field(default_factory=list)
    math_blocks: list[PlanV1MathBlock] = Field(default_factory=list)
    teacher_checkpoints: list[PlanV1TeacherCheckpoint] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    source_coverage: list[PlanV1SourceCoverage] = Field(default_factory=list)

    @field_validator("document_title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not str(value or "").strip():
            raise ValueError("document_title must not be empty")
        return value

    @field_validator("review_schedule")
    @classmethod
    def validate_schedule(cls, value: list[PlanV1ScheduleItem]) -> list[PlanV1ScheduleItem]:
        if not value:
            raise ValueError("review_schedule must not be empty")
        return value

    @model_validator(mode="after")
    def validate_task_days(self) -> "LessonReviewPlanV1":
        schedule_days = {item.day for item in self.review_schedule}
        for task in self.practice_tasks:
            if task.day not in schedule_days:
                raise ValueError("practice task day must exist in review_schedule")
        for question in self.self_check_questions:
            if question.day not in schedule_days:
                raise ValueError("self-check day must exist in review_schedule")
        return self


def validate_lesson_review_plan_v1(plan: dict[str, Any]) -> Tuple[Optional[LessonReviewPlanV1], list[str]]:
    try:
        return LessonReviewPlanV1.model_validate(plan), []
    except ValidationError as exc:
        return None, [error.get("msg", str(error)) for error in exc.errors()]


def is_lesson_review_plan_v1(plan: Any) -> bool:
    return isinstance(plan, dict) and plan.get("schema_version") == "lesson_review_plan_v1"


def _clean_text(value: object) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value or "").strip()


def _task_is_choice(task: PlanV1PracticeTask) -> bool:
    return task.task_type in {"choice", "multiple_choice"} or bool(task.options)


def _task_is_fill(task: PlanV1PracticeTask) -> bool:
    task_type = task.task_type.replace("-", "_").lower()
    return task_type in {"blank", "fill", "fill_in_blank", "fillinblank"} or "______" in task.question


def adapt_lesson_review_plan_v1_to_final_review_plan(plan: dict[str, Any]) -> dict[str, Any]:
    parsed, errors = validate_lesson_review_plan_v1(plan)
    if parsed is None:
        raise ValueError("lesson_review_plan_v1 validation failed: " + "；".join(errors[:3]))

    lesson_info = {
        "subject": parsed.audience.subject,
        "grade": parsed.audience.grade,
        "topic": parsed.document_title,
        "date": parsed.audience.lesson_date,
        "key_categories": [item.title for item in parsed.knowledge_map if _clean_text(item.title)],
    }
    tasks_by_day: dict[int, list[PlanV1PracticeTask]] = {}
    checks_by_day: dict[int, list[PlanV1SelfCheckQuestion]] = {}
    for task in parsed.practice_tasks:
        tasks_by_day.setdefault(task.day, []).append(task)
    for question in parsed.self_check_questions:
        checks_by_day.setdefault(question.day, []).append(question)

    days: list[dict[str, Any]] = []
    for schedule_item in sorted(parsed.review_schedule, key=lambda item: item.day):
        day_tasks = tasks_by_day.get(schedule_item.day, [])
        day_checks = checks_by_day.get(schedule_item.day, [])
        blanks: list[dict[str, str]] = []
        choices: list[dict[str, Any]] = []
        body_items: list[dict[str, str]] = []

        for action in schedule_item.actions:
            text = _clean_text(action)
            if text:
                body_items.append({"type": "body", "text": text})
        for output in schedule_item.outputs:
            text = _clean_text(output)
            if text:
                body_items.append({"type": "body", "text": "产出：" + text})

        for task in day_tasks:
            if _task_is_choice(task):
                choices.append(
                    {
                        "question": task.question,
                        "options": task.options,
                        "answer": task.answer,
                        "analysis": task.analysis,
                    }
                )
            elif _task_is_fill(task):
                blanks.append({"text": task.question, "answer": task.answer})
            else:
                body_items.append(
                    {
                        "type": "fill",
                        "text": task.question if "______" in task.question else task.question + "：______",
                        "answer": task.answer,
                    }
                )

        for question in day_checks:
            body_items.append(
                {
                    "type": "fill",
                    "text": question.question if "______" in question.question else question.question + "：______",
                    "answer": question.answer,
                }
            )

        days.append(
            {
                "day": schedule_item.day,
                "label": schedule_item.label or f"第{schedule_item.day}天复习",
                "goal": schedule_item.focus,
                "focus": schedule_item.focus,
                "time_minutes": schedule_item.time_minutes,
                "items": body_items,
                "blanks": blanks,
                "choices": choices,
                "completion_standard": "；".join(schedule_item.outputs),
                "self_test_phrase": day_checks[0].question if day_checks else "",
            }
        )

    return {
        "lesson_info": lesson_info,
        "days": days,
        "weak_points_summary": parsed.lesson_summary,
        "full_review_topics": [item.title for item in parsed.knowledge_map if _clean_text(item.title)],
        "quotes": [],
        "final_reminder_lines": [item for item in parsed.uncertainties if _clean_text(item)],
        "knowledge_sections": {
            "math_blocks": [block.model_dump() for block in parsed.math_blocks],
            "teacher_checkpoints": [checkpoint.model_dump() for checkpoint in parsed.teacher_checkpoints],
            "source_coverage": [coverage.model_dump() for coverage in parsed.source_coverage],
        },
    }
