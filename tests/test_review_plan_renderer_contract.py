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

    def test_renderer_dry_run_detects_visible_bare_math_after_adapter(self):
        rendered_day = {
            "offset": 1,
            "day": "当天课后复习",
            "focus": "alpha角与beta三角形的份数计算。",
            "goal": "完成检查。",
            "tasks": [],
            "blanks": [(f"第{i}题：填写______。", "答案") for i in range(1, 7)],
            "choices": [
                {
                    "question": f"选择题{i}：下列哪组是勾股数？",
                    "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                    "answer": "A",
                }
                for i in range(1, 5)
            ],
            "method_cards": [],
            "quotes": [],
        }

        with patch("review_plan_workflow.renderer_contract.adapt_plan_to_review_template") as mock_adapt:
            mock_adapt.return_value = ({}, [rendered_day], [])
            report = dry_run_review_plan_renderer(valid_plan_v1())

        self.assertFalse(report.passed)
        self.assertTrue(any(item.startswith("visible_bare_math:") for item in report.formula_failures))

    def test_renderer_dry_run_detects_empty_choice_option(self):
        plan = valid_plan_v1()
        choice = next(task for task in plan["practice_tasks"] if task["task_type"] == "choice")
        choice["options"] = ["A. 3,4,5", "B. 5,12,13", "C. 7,24,25", "D."]

        report = dry_run_review_plan_renderer(plan)

        self.assertFalse(report.passed)
        self.assertIn("rendered_choice_empty_option:0:3", report.dropped_items)


if __name__ == "__main__":
    unittest.main()
