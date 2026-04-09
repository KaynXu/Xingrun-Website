import json
import unittest
from unittest.mock import patch

import ai_processor


class _FakeChatCompletions:
    def __init__(self, content: dict):
        self.content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return type(
            "Response",
            (),
            {
                "model": kwargs.get("model", ""),
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Message",
                                (),
                                {
                                    "content": json.dumps(self.content, ensure_ascii=False),
                                },
                            )()
                        },
                    )()
                ],
            },
        )()


class _FakeClient:
    def __init__(self, content: dict):
        self.chat = type(
            "Chat",
            (),
            {"completions": _FakeChatCompletions(content)},
        )()


class AiProcessorPromptTestCase(unittest.TestCase):
    def test_plan_system_prompt_limits_formula_only_fill_ratio(self):
        self.assertIn("纯公式型填空题", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("不得超过 30%", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("至少 70% 的填空题", ai_processor.PLAN_SYSTEM_PROMPT)

    def test_parse_and_generate_plan_falls_back_to_gpt_4o_for_n1n_gpt_5_models(self):
        fake_client = _FakeClient(
            {
                "lesson_info": {},
                "days": [],
                "weekly_review_prompts": [],
            }
        )
        with patch(
            "ai_processor._load_config",
            return_value={
                "provider": "n1n",
                "n1n_model": "gpt-5.4",
                "n1n_api_key": "test-key",
                "n1n_base_url": "https://api.n1n.ai/v1",
            },
        ), patch("ai_processor._get_client", return_value=fake_client):
            ai_processor.parse_and_generate_plan("课堂总结")

        self.assertEqual(fake_client.chat.completions.last_kwargs["model"], "gpt-4o")

    def test_generate_monthly_plan_falls_back_to_gpt_4o_for_n1n_gpt_5_models(self):
        fake_client = _FakeClient(
            {
                "lesson_info": {},
                "days": [],
                "weekly_review_prompts": [],
            }
        )
        with patch(
            "ai_processor._load_config",
            return_value={
                "provider": "n1n",
                "n1n_model": "gpt-5.4",
                "n1n_api_key": "test-key",
                "n1n_base_url": "https://api.n1n.ai/v1",
            },
        ), patch("ai_processor._get_client", return_value=fake_client):
            ai_processor.generate_monthly_plan(
                [{"date": "2026-04-09", "summary": "课堂总结", "topic": "一次函数"}],
                "2026-04",
            )

        self.assertEqual(fake_client.chat.completions.last_kwargs["model"], "gpt-4o")


if __name__ == "__main__":
    unittest.main()
