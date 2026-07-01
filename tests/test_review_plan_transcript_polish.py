import unittest

from review_plan_workflow.transcript_polish import (
    build_review_plan_transcript_polish_payload,
    normalize_review_plan_transcript_polish_text,
)


class ReviewPlanTranscriptPolishTestCase(unittest.TestCase):
    def test_payload_is_correction_only_and_keeps_teacher_requirements_separate(self):
        payload = build_review_plan_transcript_polish_payload(
            raw_transcript_text="动点倒顶点距离不变，轨迹是求面。",
            subject="数学",
            grade="六年级",
            topic="动点与立体几何综合",
            teacher_requirements="压缩成一天，少一点题量",
            math_terms=["动点", "定点", "球面"],
        )

        self.assertEqual(payload["task"], "review_plan_transcript_polish")
        self.assertIn("raw_transcript", payload)
        self.assertIn("teacher_requirements", payload)
        self.assertIn("Do not create review tasks", payload["rules"])
        self.assertIn("Do not rewrite this into parent feedback", payload["rules"])

    def test_normalizer_removes_outer_markdown_without_changing_lines(self):
        self.assertEqual(
            normalize_review_plan_transcript_polish_text("```text\n第一行\n第二行\n```"),
            "第一行\n第二行",
        )


if __name__ == "__main__":
    unittest.main()
