import unittest
from unittest.mock import patch

from review_plan_workflow.renderer_contract import dry_run_review_plan_renderer
from tests.test_review_plan_plan_v1 import valid_plan_v1
from tests.review_plan_test_utils import valid_single_lesson_plan


class ReviewPlanRendererContractTestCase(unittest.TestCase):
    def test_renderer_dry_run_reports_visible_questions_and_answers(self):
        report = dry_run_review_plan_renderer(valid_plan_v1())

        self.assertTrue(report.passed, report.model_dump())
        self.assertEqual(report.canonical_visible_question_count, 10)
        self.assertEqual(report.visible_question_count, 10)
        self.assertEqual(report.answer_key_count, 10)
        self.assertFalse(report.dropped_items)
        self.assertFalse(report.formula_failures)

    def test_renderer_dry_run_detects_adapter_question_loss(self):
        with patch("review_plan_workflow.renderer_contract.adapt_plan_to_review_template") as mock_adapt:
            mock_adapt.return_value = ({}, [{"blanks": [], "choices": []}], [])
            report = dry_run_review_plan_renderer(valid_plan_v1())

        self.assertFalse(report.passed)
        self.assertEqual(report.visible_question_count, 0)
        self.assertEqual(report.canonical_visible_question_count, 10)
        self.assertIn("renderer_visible_count_mismatch:0!=10", report.dropped_items)

    def test_renderer_dry_run_detects_fallback_blank(self):
        plan = valid_single_lesson_plan(subject="数学", topic="函数")
        plan["days"] = [{"day": 1, "items": [{"type": "body", "text": "复述课堂内容。"}]}]

        report = dry_run_review_plan_renderer(plan)

        self.assertFalse(report.passed)
        self.assertEqual(report.canonical_visible_question_count, 0)
        self.assertEqual(report.visible_question_count, 1)
        self.assertTrue(any(item.startswith("renderer_fallback_blank") for item in report.dropped_items))

    def test_renderer_dry_run_detects_unresolved_math_placeholder(self):
        plan = valid_single_lesson_plan(subject="数学", topic="函数")
        plan["days"][0].setdefault("blanks", []).append({"text": "公式 {{math:missing}} 中缺少______。", "answer": "定义"})

        report = dry_run_review_plan_renderer(plan)

        self.assertFalse(report.passed)
        self.assertTrue(any("unresolved_placeholder" in item for item in report.formula_failures))


if __name__ == "__main__":
    unittest.main()
