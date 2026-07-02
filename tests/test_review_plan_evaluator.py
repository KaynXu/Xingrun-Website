import unittest

from review_plan_workflow.evaluator import build_review_plan_evaluation, evaluation_category_for_issue
from review_plan_workflow.schemas import QualityIssue, QualityReview
from review_plan_workflow.validator import ReviewPlanValidationIssue, ReviewPlanValidationResult


class ReviewPlanEvaluatorTestCase(unittest.TestCase):
    def test_maps_issue_categories_to_fixed_evaluator_taxonomy(self):
        self.assertEqual(evaluation_category_for_issue("task_actionability"), "pedagogy")
        self.assertEqual(evaluation_category_for_issue("subject_fit"), "source_confidence")
        self.assertEqual(evaluation_category_for_issue("question_quality"), "factuality")
        self.assertEqual(evaluation_category_for_issue("workload_sanity"), "workload")
        self.assertEqual(evaluation_category_for_issue("style_consistency"), "style")
        self.assertEqual(evaluation_category_for_issue("renderer"), "delivery_contract")

    def test_validator_failure_is_delivery_contract_and_blocks_pass(self):
        validator_result = ReviewPlanValidationResult(
            passed=False,
            printable_question_count=10,
            rendered_question_count=7,
            issues=[
                ReviewPlanValidationIssue(
                    severity="high",
                    category="renderer",
                    description="PDF dry run 可见题量 7 与 canonical 可打印题量 10 不一致。",
                )
            ],
        )
        local_quality = QualityReview(score=96, passed=True, must_revise=False, issues=[])

        evaluation = build_review_plan_evaluation(
            local_quality=local_quality,
            validator_result=validator_result,
        )

        self.assertFalse(evaluation.passed)
        self.assertTrue(evaluation.must_revise)
        self.assertFalse(evaluation.validator_passed)
        self.assertEqual(evaluation.score, 60)
        self.assertEqual(evaluation.issues[0].category, "delivery_contract")
        self.assertEqual(evaluation.issues[0].source, "validator")

    def test_llm_reviewer_issue_is_classified_without_hiding_local_quality(self):
        local_quality = QualityReview(score=92, passed=True, must_revise=False, issues=[])
        llm_quality = QualityReview(
            score=70,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="factuality",
                    description="选择题答案错误。",
                    suggested_fix="重写该题答案。",
                )
            ],
            revision_instructions=["重写该题答案。"],
        )

        evaluation = build_review_plan_evaluation(
            local_quality=local_quality,
            llm_quality=llm_quality,
        )

        self.assertFalse(evaluation.passed)
        self.assertTrue(evaluation.must_revise)
        self.assertTrue(evaluation.llm_review_used)
        self.assertEqual(evaluation.score, 70)
        self.assertEqual(evaluation.issues[0].category, "factuality")
        self.assertEqual(evaluation.issues[0].source, "llm_reviewer")

    def test_low_source_confidence_stays_separate_from_factuality(self):
        local_quality = QualityReview(
            score=86,
            passed=True,
            must_revise=False,
            issues=[
                QualityIssue(
                    severity="medium",
                    category="subject_fit",
                    description="课堂材料证据较弱。",
                )
            ],
        )

        evaluation = build_review_plan_evaluation(local_quality=local_quality)

        self.assertTrue(evaluation.passed)
        self.assertFalse(evaluation.must_revise)
        self.assertEqual(evaluation.issues[0].category, "source_confidence")


if __name__ == "__main__":
    unittest.main()
