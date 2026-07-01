import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from review_plan_workflow.evals.runner import (
    CHINA_COURSE_MARKERS,
    FIXTURE_ROOT,
    INTERNATIONAL_COURSE_TERMS,
    evaluate_plan_against_fixture,
    iter_fixture_paths,
    load_fixture,
    run_workflow_eval,
    run_workflow_for_fixture,
    validate_all_fixtures,
    validate_fixture_definition,
    workflow_kwargs_from_fixture,
)
from tests.review_plan_test_utils import (
    dynamic_geometry_source_brief_plan,
    text_only_low_density_review_plan,
    valid_single_lesson_plan,
)


def _extract_day_numbers(plan: dict) -> list[int]:
    days = plan.get("days") if isinstance(plan.get("days"), list) else []
    numbers: list[int] = []
    for day in days:
        if not isinstance(day, dict):
            continue
        try:
            numbers.append(int(day.get("day") or day.get("day_number")))
        except (TypeError, ValueError):
            continue
    return sorted(numbers)


def _lesson_topic(plan: dict) -> str:
    lesson_info = plan.get("lesson_info") if isinstance(plan.get("lesson_info"), dict) else {}
    return str(lesson_info.get("topic") or plan.get("topic") or plan.get("lesson_topic") or "").strip()


def _task_text(item: dict) -> str:
    return str(item.get("text") or item.get("question") or item.get("stem") or item.get("label") or "").strip()


def _iter_day_tasks(day: dict, key: str) -> list[dict]:
    values = day.get(key) if isinstance(day.get(key), list) else []
    return [item for item in values if isinstance(item, dict)]


def _printable_item_count(day: dict) -> int:
    count = 0
    for key in ("items", "blanks", "choices"):
        count += sum(1 for item in _iter_day_tasks(day, key) if _task_text(item))
    return count


def _assert_fixed_single_lesson_review_days(plan: dict, assertion: dict) -> None:
    expected_days = sorted(int(day) for day in assertion["daysExactly"])
    actual_days = _extract_day_numbers(plan)
    assert actual_days == expected_days, f"expected days {expected_days}, got {actual_days}"


def _assert_topic_contains(plan: dict, assertion: dict) -> None:
    topic = _lesson_topic(plan)
    expected = str(assertion["contains"])
    assert expected in topic, f"expected topic to contain {expected!r}, got {topic!r}"


def _assert_topic_not_empty(plan: dict, assertion: dict) -> None:
    topic = _lesson_topic(plan)
    assert topic and topic != "课后", f"expected non-empty specific topic, got {topic!r}"


def _assert_full_review_topics_minimum(plan: dict, assertion: dict) -> None:
    topics = plan.get("full_review_topics") if isinstance(plan.get("full_review_topics"), list) else []
    minimum = int(assertion["minimum"])
    assert len(topics) >= minimum, f"expected at least {minimum} full review topics, got {len(topics)}"


def _assert_minimum_printable_items_per_day(plan: dict, assertion: dict) -> None:
    minimum = int(assertion["minimum"])
    for day in plan.get("days") or []:
        count = _printable_item_count(day) if isinstance(day, dict) else 0
        assert count >= minimum, f"day {day.get('day') if isinstance(day, dict) else '?'} has {count} printable items"


def _assert_no_duplicate_printable_tasks(plan: dict, assertion: dict) -> None:
    for day in plan.get("days") or []:
        if not isinstance(day, dict):
            continue
        texts = []
        for key in ("items", "blanks", "choices"):
            texts.extend(_task_text(item) for item in _iter_day_tasks(day, key))
        normalized = [text for text in texts if text]
        assert len(normalized) == len(set(normalized)), f"day {day.get('day')} has duplicate printable tasks"


def _assert_choices_have_complete_options(plan: dict, assertion: dict) -> None:
    minimum_choices = int(assertion.get("minimumChoices", 1))
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


def _assert_no_generic_checklist_choices(plan: dict, assertion: dict) -> None:
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


def _run_fixture_assertions(plan: dict, fixture: dict) -> None:
    for assertion in fixture.get("assertions") or []:
        name = assertion.get("name")
        handler = ASSERTION_HANDLERS.get(name)
        assert handler is not None, f"unsupported fixture assertion: {name}"
        try:
            handler(plan, assertion)
        except AssertionError as exc:
            raise AssertionError(f"{name} failed: {exc}") from exc


def _only_assertion(fixture: dict, name: str) -> dict:
    assertions = [assertion for assertion in fixture.get("assertions") or [] if assertion.get("name") == name]
    assert assertions, f"missing fixture assertion: {name}"
    return {
        "assertions": assertions
    }


class ReviewPlanEvalRunnerTestCase(unittest.TestCase):
    def test_all_eval_fixtures_are_valid(self):
        report = validate_all_fixtures()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["fixture_count"], len(iter_fixture_paths()))

    def test_math_and_physics_fixtures_default_to_china_school_context(self):
        for fixture_path in iter_fixture_paths():
            fixture = load_fixture(fixture_path)
            input_payload = fixture.get("input", {})
            subject = input_payload.get("subject")
            if subject not in {"math", "physics"}:
                continue

            errors = validate_fixture_definition(fixture, fixture_path=str(fixture_path.relative_to(FIXTURE_ROOT)))
            self.assertFalse(errors)
            course_system = input_payload.get("courseSystem", "")
            self.assertTrue(any(marker in course_system for marker in CHINA_COURSE_MARKERS), fixture_path)
            input_text = str(input_payload)
            self.assertFalse(any(term in input_text for term in INTERNATIONAL_COURSE_TERMS), fixture_path)

    def test_eval_runner_passes_valid_math_plan_against_fixture(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertTrue(result["passed"], result)
        self.assertTrue(result["schema_valid"])
        self.assertTrue(result["quality"]["passed"])
        self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_eval_runner_fails_schema_invalid_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)

        result = evaluate_plan_against_fixture({"lesson_info": {"topic": "一次函数"}, "days": []}, fixture)

        self.assertFalse(result["passed"])
        self.assertFalse(result["schema_valid"])
        self.assertTrue(result["schema_errors"])

    def test_eval_runner_fails_forbidden_international_terms_in_math_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        plan["weak_points_summary"] += " A-Level"

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertFalse(result["passed"])
        default_check = next(check for check in result["checks"] if check["name"] == "no_international_course_default")
        self.assertFalse(default_check["passed"])
        self.assertEqual(default_check["forbidden_found"], ["A-Level"])

    def test_task8_dynamic_geometry_fixture_preserves_source_brief_context(self):
        fixture_path = FIXTURE_ROOT / "math" / "dynamic-geometry-source-brief.json"
        fixture = load_fixture(fixture_path)

        errors = validate_fixture_definition(fixture, fixture_path=str(fixture_path.relative_to(FIXTURE_ROOT)))
        kwargs = workflow_kwargs_from_fixture(fixture)

        self.assertFalse(errors)
        self.assertEqual(kwargs["topic"], "动点与立体几何综合")
        self.assertIn("老师强调", kwargs["summary_text"])
        self.assertIn("动点 P", kwargs["summary_text"])
        self.assertIn("空间轨迹判断", kwargs["weak_points"])
        self.assertEqual(fixture["input"]["generation_options"]["review_days"], [1, 2, 7, 14, 30])
        self.assertIn("真实数学判断", fixture["input"]["generation_options"]["user_requirements"])

    def test_task8_dynamic_geometry_assertions_pass_realistic_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "dynamic-geometry-source-brief.json"
        fixture = load_fixture(fixture_path)
        plan = dynamic_geometry_source_brief_plan()

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertTrue(result["passed"], result)
        _run_fixture_assertions(plan, fixture)

    def test_task8_dynamic_geometry_assertions_reject_choice_regressions(self):
        fixture_path = FIXTURE_ROOT / "math" / "dynamic-geometry-source-brief.json"
        fixture = load_fixture(fixture_path)
        cases = {
            "choices_have_complete_options": lambda plan: plan["days"][0]["choices"][0].update(
                {"options": ["A. 球面"], "answer": "A"}
            ),
            "no_generic_checklist_choices": lambda plan: plan["days"][0]["choices"][0].update(
                {
                    "question": "今天应选择哪一组执行清单？",
                    "options": ["A. 先看固定量", "B. 检查边界", "C. 完成复盘", "D. 执行清单"],
                    "answer": "A",
                }
            ),
        }

        for assertion_name, mutate in cases.items():
            with self.subTest(assertion_name=assertion_name):
                plan = dynamic_geometry_source_brief_plan()
                mutate(plan)
                with self.assertRaisesRegex(AssertionError, assertion_name):
                    _run_fixture_assertions(plan, _only_assertion(fixture, assertion_name))

    def test_task8_text_only_low_density_assertions_pass_dense_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "text-only-low-density-review-plan.json"
        fixture = load_fixture(fixture_path)
        plan = text_only_low_density_review_plan()

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertTrue(result["passed"], result)
        _run_fixture_assertions(plan, fixture)

    def test_task8_text_only_low_density_assertions_reject_known_failures(self):
        fixture_path = FIXTURE_ROOT / "math" / "text-only-low-density-review-plan.json"
        fixture = load_fixture(fixture_path)
        cases = {
            "topic_not_empty": lambda plan: plan["lesson_info"].update({"topic": ""}),
            "full_review_topics_minimum": lambda plan: plan.update({"full_review_topics": ["等式判断"]}),
            "minimum_printable_items_per_day": lambda plan: plan["days"][0].update(
                {"items": [], "blanks": plan["days"][0]["blanks"][:1], "choices": []}
            ),
            "no_duplicate_printable_tasks": lambda plan: plan["days"][0]["blanks"].append(
                copy.deepcopy(plan["days"][0]["blanks"][0])
            ),
        }

        for assertion_name, mutate in cases.items():
            with self.subTest(assertion_name=assertion_name):
                plan = text_only_low_density_review_plan()
                mutate(plan)
                with self.assertRaisesRegex(AssertionError, assertion_name):
                    _run_fixture_assertions(plan, _only_assertion(fixture, assertion_name))

    def test_workflow_kwargs_from_fixture_preserves_subject_context(self):
        fixture_path = FIXTURE_ROOT / "physics" / "mechanics-electricity-units-experiment.json"
        fixture = load_fixture(fixture_path)

        kwargs = workflow_kwargs_from_fixture(fixture, provider="deepseek", model="deepseek-v4-pro")

        self.assertEqual(kwargs["subject"], "physics")
        self.assertEqual(kwargs["grade"], "九年级")
        self.assertIn("中国初中物理", kwargs["summary_text"])
        self.assertIn("力学受力分析", kwargs["weak_points"])
        self.assertTrue(kwargs["include_usage"])

    def test_workflow_eval_uses_generator_and_evaluates_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)
        calls = []

        def fake_generator(**kwargs):
            calls.append(kwargs)
            return valid_single_lesson_plan(subject="数学", topic="一次函数"), {
                "provider": "fake",
                "model": "fake-model",
                "input_tokens": 1,
                "output_tokens": 2,
            }

        result = run_workflow_for_fixture(fixture, fixture_path=str(fixture_path), generator=fake_generator)

        self.assertTrue(result["passed"], result)
        self.assertEqual(result["status"], "evaluated")
        self.assertEqual(result["usage"]["provider"], "fake")
        self.assertEqual(calls[0]["subject"], "math")
        self.assertTrue(result["evaluation"]["passed"])

    def test_workflow_eval_collects_filtered_fixture_report(self):
        def fake_generator(**kwargs):
            return valid_single_lesson_plan(subject="数学", topic="一次函数"), {}

        report = run_workflow_eval(
            fixture_filters=["math/algebra-weakness-6-week.json"],
            generator=fake_generator,
        )

        self.assertTrue(report["passed"], report)
        self.assertEqual(report["fixture_count"], 1)
        self.assertEqual(report["mode"], "workflow")
        self.assertEqual(report["results"][0]["status"], "evaluated")

    def test_workflow_eval_returns_generation_error_without_crashing(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)

        def failing_generator(**kwargs):
            raise RuntimeError("missing api key")

        result = run_workflow_for_fixture(fixture, fixture_path=str(fixture_path), generator=failing_generator)

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "generation_failed")
        self.assertIn("missing api key", result["error"])


if __name__ == "__main__":
    unittest.main()
