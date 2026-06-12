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
    validate_all_fixtures,
    validate_fixture_definition,
)
from tests.review_plan_test_utils import valid_single_lesson_plan


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


if __name__ == "__main__":
    unittest.main()

