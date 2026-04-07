import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_processor


class _FakeChatCompletions:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return type(
            "Response",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Message",
                                (),
                                {
                                    "content": json.dumps(
                                        {
                                            "class_summary": "示例班级反馈",
                                            "student_entries": [
                                                {
                                                    "student_id": 1,
                                                    "name": "张三",
                                                    "text": "示例学生反馈",
                                                }
                                            ],
                                        },
                                        ensure_ascii=False,
                                    )
                                },
                            )()
                        },
                    )()
                ]
            },
        )()


class _FakeClient:
    def __init__(self):
        self.chat = type(
            "Chat",
            (),
            {"completions": _FakeChatCompletions()},
        )()


class ClassFeedbackAiPromptTestCase(unittest.TestCase):
    def test_system_prompt_requires_teacher_to_parent_tone_during_cold_start(self):
        fake_client = _FakeClient()
        with patch("ai_processor._get_client", return_value=fake_client), patch(
            "ai_processor._get_chat_model", return_value="gpt-4o"
        ):
            ai_processor.generate_class_feedback_bundle(
                class_name="冷启动验收班",
                teacher_name="Kayn",
                start_date="2026-04-05",
                end_date="2026-04-05",
                source_summary="{}",
                stage_notes={"recent_confirmed_class_summaries": []},
                students=[
                    {
                        "student_id": 1,
                        "name": "张三",
                        "stage_highlight": {"labels": [], "note": ""},
                        "previous_baseline": None,
                    }
                ],
            )

        messages = fake_client.chat.completions.last_kwargs["messages"]
        system_prompt = messages[0]["content"]

        self.assertIn("直接发给家长", system_prompt)
        self.assertIn("自然口吻", system_prompt)
        self.assertIn("不要写成系统总结或阶段报告", system_prompt)
        self.assertIn("没有明确历史基线", system_prompt)
        self.assertIn("不要写“比上次”", system_prompt)
        self.assertIn("班级总评也要像老师发给家长群的消息", system_prompt)

    def test_user_prompt_marks_cold_start_mode_when_no_confirmed_history_exists(self):
        fake_client = _FakeClient()
        with patch("ai_processor._get_client", return_value=fake_client), patch(
            "ai_processor._get_chat_model", return_value="gpt-4o"
        ):
            ai_processor.generate_class_feedback_bundle(
                class_name="冷启动验收班",
                teacher_name="Kayn",
                start_date="2026-04-05",
                end_date="2026-04-05",
                source_summary="{}",
                stage_notes={"recent_confirmed_class_summaries": []},
                students=[
                    {
                        "student_id": 1,
                        "name": "张三",
                        "stage_highlight": {"labels": [], "note": ""},
                        "previous_baseline": None,
                    }
                ],
            )

        messages = fake_client.chat.completions.last_kwargs["messages"]
        user_prompt = json.loads(messages[1]["content"])

        self.assertTrue(user_prompt["cold_start_mode"])
        self.assertEqual(user_prompt["history_readiness_level"], "L0")


if __name__ == "__main__":
    unittest.main()
