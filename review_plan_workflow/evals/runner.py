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
    checks_passed = all(result["passed"] for result in check_results)
    passed = not definition_errors and schema_valid and quality.passed and checks_passed

    return {
        "fixture": fixture_path,
        "passed": passed,
        "definition_errors": definition_errors,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "quality": quality.model_dump(),
        "checks": check_results,
    }


def workflow_kwargs_from_fixture(fixture: dict[str, Any], *, provider: str = "", model: str = "") -> dict[str, Any]:
    input_payload = fixture.get("input") if isinstance(fixture.get("input"), dict) else {}
    known_weaknesses = [str(item) for item in _list_value(input_payload.get("knownWeaknesses"))]
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
