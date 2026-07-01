from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from review_plan_workflow.quality_gate import review_single_lesson_plan
from review_plan_workflow.schemas import validate_final_review_plan


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
CHINA_COURSE_MARKERS = ("中国", "小学", "初中", "高中", "中考", "高考", "校内")
INTERNATIONAL_COURSE_TERMS = (
    "A-Level",
    "IGCSE",
    "AP",
    "IB",
    "international syllabus",
    "exam board",
    "国际课程",
    "考试局",
)
CHECK_OPERATORS = {
    "containsAny",
    "containsAll",
    "notContainsAny",
    "daysExactly",
    "minQualityScore",
    "schemaValid",
}
ASSERTION_NAMES = {
    "fixed_single_lesson_review_days",
    "topic_contains",
    "topic_not_empty",
    "full_review_topics_minimum",
    "minimum_printable_items_per_day",
    "choices_have_complete_options",
    "no_duplicate_printable_tasks",
    "no_generic_checklist_choices",
}


def iter_fixture_paths(root: Path = FIXTURE_ROOT) -> list[Path]:
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative_fixture_path(path: Path, root: Path = FIXTURE_ROOT) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _stringify(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _subject_from_fixture(fixture: dict[str, Any]) -> str:
    input_payload = fixture.get("input") if isinstance(fixture.get("input"), dict) else {}
    return str(input_payload.get("subject") or "").lower()


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _check_terms(value: Any) -> list[str]:
    return [str(item) for item in _list_value(value)]


def validate_fixture_definition(fixture: dict[str, Any], *, fixture_path: str = "") -> list[str]:
    errors: list[str] = []
    label = fixture_path or fixture.get("name") or "<fixture>"

    input_payload = fixture.get("input")
    if not isinstance(input_payload, dict):
        errors.append(f"{label}: input must be an object")
        input_payload = {}

    expected_criteria = fixture.get("expectedCriteria")
    if not isinstance(expected_criteria, list) or not expected_criteria:
        errors.append(f"{label}: expectedCriteria must be a non-empty list")

    checks = fixture.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append(f"{label}: checks must be a non-empty list")
        checks = []

    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            errors.append(f"{label}: checks[{index}] must be an object")
            continue
        if not isinstance(check.get("name"), str) or not check.get("name"):
            errors.append(f"{label}: checks[{index}] must include a name")
        operators = CHECK_OPERATORS & set(check.keys())
        if not operators:
            errors.append(f"{label}: checks[{index}] must include one supported operator")
        if len(operators) > 1:
            errors.append(f"{label}: checks[{index}] must include only one supported operator")

    assertions = fixture.get("assertions")
    if assertions is not None:
        if not isinstance(assertions, list):
            errors.append(f"{label}: assertions must be a list when present")
        else:
            for index, assertion in enumerate(assertions, start=1):
                if not isinstance(assertion, dict):
                    errors.append(f"{label}: assertions[{index}] must be an object")
                    continue
                name = assertion.get("name")
                if not isinstance(name, str) or not name:
                    errors.append(f"{label}: assertions[{index}] must include a name")
                elif name not in ASSERTION_NAMES:
                    errors.append(f"{label}: assertions[{index}] uses unsupported assertion {name}")

    subject = str(input_payload.get("subject") or "").lower()
    allow_international = bool(fixture.get("allowInternationalCourse"))
    if subject in {"math", "physics"} and not allow_international:
        course_system = str(input_payload.get("courseSystem") or "")
        if course_system and not any(marker in course_system for marker in CHINA_COURSE_MARKERS):
            errors.append(f"{label}: math/physics fixtures must default to China school course context")
        input_text = _stringify(input_payload)
        forbidden_terms = [term for term in INTERNATIONAL_COURSE_TERMS if term in input_text]
        if forbidden_terms:
            errors.append(
                f"{label}: math/physics fixture input contains international-course terms: "
                + ", ".join(forbidden_terms)
            )

    return errors


def _extract_day_numbers(plan: dict[str, Any]) -> list[int]:
    days = plan.get("days") if isinstance(plan.get("days"), list) else []
    numbers: list[int] = []
    for day in days:
        if isinstance(day, dict):
            try:
                numbers.append(int(day.get("day") or day.get("day_number")))
            except (TypeError, ValueError):
                continue
    return sorted(numbers)


def _lesson_topic(plan: dict[str, Any]) -> str:
    lesson_info = plan.get("lesson_info") if isinstance(plan.get("lesson_info"), dict) else {}
    return str(lesson_info.get("topic") or plan.get("topic") or plan.get("lesson_topic") or "").strip()


def _task_text(item: dict[str, Any]) -> str:
    return str(item.get("text") or item.get("question") or item.get("stem") or item.get("label") or "").strip()


def _iter_day_tasks(day: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = day.get(key) if isinstance(day.get(key), list) else []
    return [item for item in values if isinstance(item, dict)]


def _printable_item_count(day: dict[str, Any]) -> int:
    count = 0
    for key in ("items", "blanks", "choices"):
        count += sum(1 for item in _iter_day_tasks(day, key) if _task_text(item))
    return count


def _assert_fixed_single_lesson_review_days(plan: dict[str, Any], assertion: dict[str, Any]) -> None:
    expected_days = sorted(int(day) for day in _list_value(assertion.get("daysExactly")))
    actual_days = _extract_day_numbers(plan)
    assert actual_days == expected_days, f"expected days {expected_days}, got {actual_days}"


def _assert_topic_contains(plan: dict[str, Any], assertion: dict[str, Any]) -> None:
    topic = _lesson_topic(plan)
    expected = str(assertion.get("contains") or "")
    assert expected in topic, f"expected topic to contain {expected!r}, got {topic!r}"


def _assert_topic_not_empty(plan: dict[str, Any], assertion: dict[str, Any]) -> None:
    topic = _lesson_topic(plan)
    assert topic and topic != "课后", f"expected non-empty specific topic, got {topic!r}"


def _assert_full_review_topics_minimum(plan: dict[str, Any], assertion: dict[str, Any]) -> None:
    topics = plan.get("full_review_topics") if isinstance(plan.get("full_review_topics"), list) else []
    minimum = int(assertion.get("minimum") or 0)
    assert len(topics) >= minimum, f"expected at least {minimum} full review topics, got {len(topics)}"


def _assert_minimum_printable_items_per_day(plan: dict[str, Any], assertion: dict[str, Any]) -> None:
    minimum = int(assertion.get("minimum") or 0)
    for day in plan.get("days") or []:
        count = _printable_item_count(day) if isinstance(day, dict) else 0
        assert count >= minimum, f"day {day.get('day') if isinstance(day, dict) else '?'} has {count} printable items"


def _assert_no_duplicate_printable_tasks(plan: dict[str, Any], assertion: dict[str, Any]) -> None:
    for day in plan.get("days") or []:
        if not isinstance(day, dict):
            continue
        texts = []
        for key in ("items", "blanks", "choices"):
            texts.extend(_task_text(item) for item in _iter_day_tasks(day, key))
        normalized = [text for text in texts if text]
        assert len(normalized) == len(set(normalized)), f"day {day.get('day')} has duplicate printable tasks"


def _assert_choices_have_complete_options(plan: dict[str, Any], assertion: dict[str, Any]) -> None:
    minimum_choices = int(assertion.get("minimumChoices") or 1)
    choices = []
    for day in plan.get("days") or []:
        if isinstance(day, dict):
            choices.extend(_iter_day_tasks(day, "choices"))
    assert len(choices) >= minimum_choices, f"expected at least {minimum_choices} choices, got {len(choices)}"
    for choice in choices:
        question = str(choice.get("question") or choice.get("stem") or "").strip()
        options = [str(option or "").strip() for option in choice.get("options", [])]
        answer = str(choice.get("answer") or "").strip()
        option_heads = {option[:1].upper() for option in options if option}
        assert question, "choice question is empty"
        assert len([option for option in options if option]) >= 4, f"choice {question!r} has incomplete options"
        assert answer[:1].upper() in option_heads, f"choice {question!r} answer {answer!r} is not in options"


def _assert_no_generic_checklist_choices(plan: dict[str, Any], assertion: dict[str, Any]) -> None:
    for day in plan.get("days") or []:
        if not isinstance(day, dict):
            continue
        for choice in _iter_day_tasks(day, "choices"):
            question = str(choice.get("question") or choice.get("stem") or "")
            options = " ".join(str(option or "") for option in choice.get("options", []))
            choice_text = f"{question} {options}"
            checklist_pair = "先看固定量" in choice_text and "检查边界" in choice_text
            generic_phrase = any(token in choice_text for token in ("执行清单", "完成复盘", "完成今日复习"))
            assert not (checklist_pair or generic_phrase), f"choice is checklist-like: {choice_text}"


ASSERTION_HANDLERS = {
    "fixed_single_lesson_review_days": _assert_fixed_single_lesson_review_days,
    "topic_contains": _assert_topic_contains,
    "topic_not_empty": _assert_topic_not_empty,
    "full_review_topics_minimum": _assert_full_review_topics_minimum,
    "minimum_printable_items_per_day": _assert_minimum_printable_items_per_day,
    "choices_have_complete_options": _assert_choices_have_complete_options,
    "no_duplicate_printable_tasks": _assert_no_duplicate_printable_tasks,
    "no_generic_checklist_choices": _assert_no_generic_checklist_choices,
}


def evaluate_fixture_assertions(plan: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    assertions = fixture.get("assertions") if isinstance(fixture.get("assertions"), list) else []
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        name = str(assertion.get("name") or "unnamed_assertion")
        handler = ASSERTION_HANDLERS.get(name)
        if handler is None:
            results.append({"name": name, "passed": False, "error": "unsupported fixture assertion"})
            continue
        try:
            handler(plan, assertion)
            results.append({"name": name, "passed": True})
        except AssertionError as exc:
            results.append({"name": name, "passed": False, "error": str(exc)})
    return results


def _evaluate_check(
    check: dict[str, Any],
    *,
    plan_text: str,
    plan: dict[str, Any],
    quality_score: int,
    schema_valid: bool,
) -> dict[str, Any]:
    name = str(check.get("name") or "unnamed_check")

    if "containsAny" in check:
        terms = _check_terms(check.get("containsAny"))
        matched = [term for term in terms if term in plan_text]
        return {"name": name, "passed": bool(matched), "operator": "containsAny", "matched": matched, "expected": terms}

    if "containsAll" in check:
        terms = _check_terms(check.get("containsAll"))
        missing = [term for term in terms if term not in plan_text]
        return {"name": name, "passed": not missing, "operator": "containsAll", "missing": missing, "expected": terms}

    if "notContainsAny" in check:
        terms = _check_terms(check.get("notContainsAny"))
        forbidden_found = [term for term in terms if term in plan_text]
        return {
            "name": name,
            "passed": not forbidden_found,
            "operator": "notContainsAny",
            "forbidden_found": forbidden_found,
            "expected_absent": terms,
        }

    if "daysExactly" in check:
        expected_days = sorted(int(day) for day in _list_value(check.get("daysExactly")))
        actual_days = _extract_day_numbers(plan)
        return {
            "name": name,
            "passed": actual_days == expected_days,
            "operator": "daysExactly",
            "expected": expected_days,
            "actual": actual_days,
        }

    if "minQualityScore" in check:
        expected_score = int(check.get("minQualityScore"))
        return {
            "name": name,
            "passed": quality_score >= expected_score,
            "operator": "minQualityScore",
            "expected": expected_score,
            "actual": quality_score,
        }

    if "schemaValid" in check:
        expected_valid = bool(check.get("schemaValid"))
        return {
            "name": name,
            "passed": schema_valid is expected_valid,
            "operator": "schemaValid",
            "expected": expected_valid,
            "actual": schema_valid,
        }

    return {"name": name, "passed": False, "operator": "unknown"}


def evaluate_plan_against_fixture(plan: dict[str, Any], fixture: dict[str, Any], *, fixture_path: str = "") -> dict[str, Any]:
    definition_errors = validate_fixture_definition(fixture, fixture_path=fixture_path)
    _, schema_errors = validate_final_review_plan(plan)
    schema_valid = not schema_errors
    subject = _subject_from_fixture(fixture)
    quality = review_single_lesson_plan(plan, subject=subject)
    plan_text = _stringify(plan)

    checks = list(fixture.get("checks") if isinstance(fixture.get("checks"), list) else [])
    if subject in {"math", "physics"} and not fixture.get("allowInternationalCourse"):
        checks.append({"name": "no_international_course_default", "notContainsAny": list(INTERNATIONAL_COURSE_TERMS)})

    check_results = [
        _evaluate_check(
            check,
            plan_text=plan_text,
            plan=plan,
            quality_score=quality.score,
            schema_valid=schema_valid,
        )
        for check in checks
        if isinstance(check, dict)
    ]
    assertion_results = evaluate_fixture_assertions(plan, fixture)
    checks_passed = all(result["passed"] for result in check_results)
    assertions_passed = all(result["passed"] for result in assertion_results)
    passed = not definition_errors and schema_valid and quality.passed and checks_passed and assertions_passed

    return {
        "fixture": fixture_path,
        "passed": passed,
        "definition_errors": definition_errors,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "quality": quality.model_dump(),
        "checks": check_results,
        "assertions": assertion_results,
    }


def workflow_kwargs_from_fixture(fixture: dict[str, Any], *, provider: str = "", model: str = "") -> dict[str, Any]:
    input_payload = fixture.get("input") if isinstance(fixture.get("input"), dict) else {}
    known_weaknesses = [str(item) for item in _list_value(input_payload.get("knownWeaknesses"))]
    generation_options = input_payload.get("generation_options")
    if not isinstance(generation_options, dict):
        generation_options = input_payload.get("generationOptions")
    if not isinstance(generation_options, dict):
        generation_options = {}
    summary_lines = [
        f"fixture: {fixture.get('name') or ''}",
        f"course_system: {input_payload.get('courseSystem') or ''}",
        f"target: {input_payload.get('target') or ''}",
        f"student_level: {input_payload.get('studentLevel') or ''}",
        f"timeframe: {_stringify(input_payload.get('timeframe') or {})}",
        f"availability: {_stringify(input_payload.get('availability') or {})}",
        "known_weaknesses: " + "；".join(known_weaknesses),
        "expected_criteria: " + "；".join(str(item) for item in _list_value(fixture.get("expectedCriteria"))),
    ]
    summary_text = str(input_payload.get("summary_text") or input_payload.get("summaryText") or "\n".join(summary_lines))
    topic = str(input_payload.get("topic") or input_payload.get("target") or (known_weaknesses[0] if known_weaknesses else "") or fixture.get("name") or "")
    return {
        "summary_text": summary_text,
        "subject": str(input_payload.get("subject") or ""),
        "grade": str(input_payload.get("grade") or input_payload.get("studentLevel") or ""),
        "topic": topic,
        "weak_points": "；".join(known_weaknesses),
        "lesson_date": str(input_payload.get("lessonDate") or input_payload.get("lesson_date") or ""),
        "provider": provider,
        "model": model,
        "generation_options": generation_options,
        "include_usage": True,
    }


def run_workflow_for_fixture(
    fixture: dict[str, Any],
    *,
    fixture_path: str = "",
    provider: str = "",
    model: str = "",
    generator: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    errors = validate_fixture_definition(fixture, fixture_path=fixture_path)
    if errors:
        return {
            "fixture": fixture_path,
            "passed": False,
            "status": "invalid_fixture",
            "definition_errors": errors,
        }

    workflow_kwargs = workflow_kwargs_from_fixture(fixture, provider=provider, model=model)
    generator_fn = generator
    if generator_fn is None:
        from review_plan_workflow.service import generate_single_lesson_review_plan

        generator_fn = generate_single_lesson_review_plan

    try:
        generated = generator_fn(**workflow_kwargs)
        if isinstance(generated, tuple):
            plan, usage = generated
        else:
            plan, usage = generated, {}
        evaluation = evaluate_plan_against_fixture(plan, fixture, fixture_path=fixture_path)
        return {
            "fixture": fixture_path,
            "passed": bool(evaluation.get("passed")),
            "status": "evaluated",
            "workflow_input": {key: value for key, value in workflow_kwargs.items() if key != "include_usage"},
            "usage": usage,
            "evaluation": evaluation,
            "plan": plan,
        }
    except Exception as exc:
        return {
            "fixture": fixture_path,
            "passed": False,
            "status": "generation_failed",
            "workflow_input": {key: value for key, value in workflow_kwargs.items() if key != "include_usage"},
            "error": str(exc),
        }


def run_workflow_eval(
    *,
    root: Path = FIXTURE_ROOT,
    fixture_filters: list[str] | None = None,
    provider: str = "",
    model: str = "",
    generator: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    fixture_filters = fixture_filters or []
    results = []
    for fixture_path in iter_fixture_paths(root):
        relative_path = _relative_fixture_path(fixture_path, root)
        if fixture_filters and not any(filter_value in relative_path for filter_value in fixture_filters):
            continue
        fixture = load_fixture(fixture_path)
        results.append(
            run_workflow_for_fixture(
                fixture,
                fixture_path=relative_path,
                provider=provider,
                model=model,
                generator=generator,
            )
        )

    return {
        "passed": bool(results) and all(result.get("passed") for result in results),
        "fixture_count": len(results),
        "mode": "workflow",
        "results": results,
    }


def validate_all_fixtures(root: Path = FIXTURE_ROOT) -> dict[str, Any]:
    results = []
    for fixture_path in iter_fixture_paths(root):
        fixture = load_fixture(fixture_path)
        errors = validate_fixture_definition(fixture, fixture_path=_relative_fixture_path(fixture_path, root))
        results.append({"fixture": _relative_fixture_path(fixture_path, root), "passed": not errors, "errors": errors})
    return {
        "passed": all(result["passed"] for result in results),
        "fixture_count": len(results),
        "mode": "fixture_validation",
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run review-plan eval fixtures.")
    parser.add_argument("--fixtures-root", type=Path, default=FIXTURE_ROOT)
    parser.add_argument("--validate-fixtures-only", action="store_true")
    parser.add_argument("--run-workflow", action="store_true", help="Generate plans from fixtures before evaluating them.")
    parser.add_argument("--fixture", action="append", default=[], help="Relative fixture path substring to run. Can be repeated.")
    parser.add_argument("--provider", default="", help="Optional LLM provider override for --run-workflow.")
    parser.add_argument("--model", default="", help="Optional LLM model override for --run-workflow.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args(argv)

    if args.run_workflow:
        report = run_workflow_eval(
            root=args.fixtures_root,
            fixture_filters=args.fixture,
            provider=args.provider,
            model=args.model,
        )
    else:
        report = validate_all_fixtures(args.fixtures_root)

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
