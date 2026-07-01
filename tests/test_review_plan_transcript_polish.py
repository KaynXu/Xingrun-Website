import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ai_processor
from review_plan_workflow.transcript_polish import (
    REVIEW_PLAN_TRANSCRIPT_POLISH_SYSTEM_PROMPT,
    build_review_plan_transcript_polish_payload,
    normalize_review_plan_transcript_polish_text,
    review_plan_transcript_source_text_hash,
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

    def test_source_text_hash_is_stable(self):
        first = review_plan_transcript_source_text_hash("动点与立体几何综合")
        second = review_plan_transcript_source_text_hash("动点与立体几何综合")
        other = review_plan_transcript_source_text_hash("一次函数")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(len(first), len("sha256:") + 64)
        self.assertNotEqual(first, other)

    @patch("ai_processor._get_client")
    def test_polish_prompt_enforces_correction_only_guardrails(self, mock_get_client):
        create = Mock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="润色后的转写"))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
                model="gpt-5.5",
            )
        )
        mock_get_client.return_value = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        text = ai_processor.polish_review_plan_transcript(
            raw_transcript_text="动点倒顶点距离不变，轨迹是求面。",
            subject="数学",
            grade="六年级",
            topic="动点与立体几何综合",
            teacher_requirements="压缩成一天，少一点题量",
            provider="openai",
            model="gpt-5.5",
        )

        self.assertEqual(text, "润色后的转写")
        self.assertEqual(create.call_count, 1)
        messages = create.call_args.kwargs["messages"]
        self.assertEqual(messages[0]["role"], "system")
        system_prompt = messages[0]["content"]
        self.assertEqual(system_prompt, REVIEW_PLAN_TRANSCRIPT_POLISH_SYSTEM_PROMPT)
        self.assertIn("Only correct ASR recognition errors, punctuation, and light sentence boundaries.", system_prompt)
        self.assertIn("Do not change meaning.", system_prompt)
        self.assertIn("Do not invent facts, topics, students, formulas, or examples.", system_prompt)
        self.assertIn("Do not rewrite this into parent feedback.", system_prompt)
        self.assertIn("Do not create review tasks.", system_prompt)
        self.assertIn("Do not compress or expand content to satisfy teacher requirements.", system_prompt)
        self.assertIn("Return polished transcript text only.", system_prompt)


if __name__ == "__main__":
    unittest.main()
