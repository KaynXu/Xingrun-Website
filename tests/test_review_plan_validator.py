import unittest
from unittest.mock import patch

from review_plan_workflow.schemas import LessonSourcePack
from review_plan_workflow.validator import validate_review_plan_delivery
from tests.test_review_plan_plan_v1 import valid_plan_v1


class ReviewPlanValidatorTestCase(unittest.TestCase):
    def test_validator_accepts_plan_v1_after_compatibility_adapter(self):
        result = validate_review_plan_delivery(
            valid_plan_v1(),
            required_review_days=[1],
            constraints={"requested_question_count": 10},
            source_pack=LessonSourcePack(
                source_id="src-1",
                segments=[{"id": "seg-1", "text": "勾股数课堂", "offset_start": 0, "offset_end": 5}],
            ),
        )

        self.assertTrue(result.passed, result.model_dump())
        self.assertEqual(result.printable_question_count, 10)
        self.assertEqual(result.rendered_question_count, 10)

    def test_validator_blocks_teacher_question_count_mismatch(self):
        result = validate_review_plan_delivery(
            valid_plan_v1(),
            required_review_days=[1],
            constraints={"requested_question_count": 9},
        )

        self.assertFalse(result.passed)
        self.assertTrue(any(issue.category == "constraints" for issue in result.issues))

    def test_validator_blocks_renderer_dry_run_question_loss(self):
        with patch("review_plan_workflow.validator.adapt_plan_to_review_template") as mock_adapt:
            mock_adapt.return_value = ({}, [{"blanks": [], "choices": []}], [])
            result = validate_review_plan_delivery(
                valid_plan_v1(),
                required_review_days=[1],
                constraints={"requested_question_count": 10},
            )

        self.assertFalse(result.passed)
        self.assertEqual(result.rendered_question_count, 0)
        self.assertTrue(any(issue.category == "renderer" for issue in result.issues))

    def test_validator_blocks_unknown_source_coverage_segment(self):
        plan = valid_plan_v1()
        plan["source_coverage"] = [{"source_segment_id": "missing-seg", "covered_by": ["k1"]}]

        result = validate_review_plan_delivery(
            plan,
            required_review_days=[1],
            constraints={"requested_question_count": 10},
            source_pack=LessonSourcePack(
                source_id="src-1",
                segments=[{"id": "seg-1", "text": "勾股数课堂", "offset_start": 0, "offset_end": 5}],
            ),
        )

        self.assertFalse(result.passed)
        self.assertTrue(any(issue.category == "source_coverage" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
