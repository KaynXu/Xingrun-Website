import json
import types
import unittest
from unittest.mock import patch

from pydantic import ValidationError

import ai_processor


def _response(payload: dict):
    return types.SimpleNamespace(
        model="memory-model",
        usage=types.SimpleNamespace(prompt_tokens=12, completion_tokens=8),
        choices=[
            types.SimpleNamespace(
                message=types.SimpleNamespace(
                    content=json.dumps(payload, ensure_ascii=False),
                )
            )
        ],
    )


class ClassCommentaryMemoryAiTest(unittest.TestCase):
    def test_learning_graph_extractor_explicitly_requests_lowercase_json(self):
        captured = {}
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=lambda **kwargs: captured.update(kwargs) or _response(
                        {
                            "schema_version": "student_learning_event.v1",
                            "items": [],
                        }
                    )
                )
            )
        )

        with patch.object(
            ai_processor,
            "_get_class_commentary_client",
            return_value=client,
        ):
            payload = ai_processor.extract_class_commentary_learning_events(
                extraction_input={"feedback_text": "小王今天计算稳定."},
                provider="openai",
                model="memory-model",
            )

        self.assertEqual(payload["items"], [])
        self.assertIn("valid json object", captured["messages"][0]["content"])
        self.assertEqual(captured["response_format"], {"type": "json_object"})

    def test_extractor_uses_frozen_input_and_returns_validated_signals(self):
        captured = {}
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=lambda **kwargs: captured.update(kwargs) or _response(
                        {
                            "items": [
                                {
                                    "memory_type": "teacher_style",
                                    "memory_text": "先肯定已经做到的部分, 再说明问题.",
                                    "confidence": 0.91,
                                    "support": ["老师将批评句前移入肯定句之后"],
                                },
                                {
                                    "memory_type": "student_fact",
                                    "student_name": "小林",
                                    "student_id_hint": 7,
                                    "memory_text": "绝对值分类讨论仍会遗漏边界条件.",
                                    "confidence": 0.86,
                                    "support": ["确认转写", "老师终稿"],
                                },
                                {
                                    "memory_type": "evaluation_only",
                                    "memory_text": "本周临时调整上课时间.",
                                    "reason": "one_off_arrangement",
                                    "confidence": 0.98,
                                    "support": ["老师终稿"],
                                },
                            ]
                        }
                    )
                )
            )
        )
        frozen_input = {
            "revision_id": 12,
            "attending_roster": [{"student_id": 7, "student_name": "小林"}],
            "teacher_final": "小林本周需要继续检查绝对值的边界条件.",
        }

        with patch.object(ai_processor, "_get_class_commentary_client", return_value=client):
            payload, usage = ai_processor.extract_class_commentary_memory_signals(
                extraction_input=frozen_input,
                provider="openai",
                model="memory-model",
                include_usage=True,
            )

        self.assertEqual([item["memory_type"] for item in payload["items"]], [
            "teacher_style",
            "student_fact",
            "evaluation_only",
        ])
        self.assertEqual(payload["items"][1]["student_id_hint"], 7)
        self.assertEqual(usage["input_tokens"], 12)
        self.assertEqual(usage["output_tokens"], 8)
        self.assertEqual(captured["temperature"], 0)
        self.assertEqual(captured["response_format"], {"type": "json_object"})
        self.assertEqual(
            json.loads(captured["messages"][1]["content"]),
            frozen_input,
        )
        self.assertIn("Do not choose or invent organization", captured["messages"][0]["content"])

    def test_extractor_rejects_unknown_signal_types_and_extra_scope_fields(self):
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=lambda **_: _response(
                        {
                            "items": [
                                {
                                    "memory_type": "knowledge_graph_edge",
                                    "memory_text": "not allowed",
                                    "organization_id": 99,
                                    "support": [],
                                }
                            ]
                        }
                    )
                )
            )
        )

        with patch.object(ai_processor, "_get_class_commentary_client", return_value=client):
            with self.assertRaises(ValidationError):
                ai_processor.extract_class_commentary_memory_signals(
                    extraction_input={"revision_id": 1},
                    provider="openai",
                    model="memory-model",
                )

    def test_skill_candidate_generator_uses_only_the_supplied_frozen_input(self):
        captured = {}
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=lambda **kwargs: captured.update(kwargs) or _response(
                        {
                            "candidate_content": "# Skill\n\nUse short paragraphs.",
                            "change_summary": ["Shorten paragraphs."],
                            "incorporated_memory_record_ids": [7],
                            "known_risks": [],
                        }
                    )
                )
            )
        )
        frozen_input = {
            "base_skill": {"content": "# Skill"},
            "style_rules": [{"memory_record_id": 7, "memory_text": "Shorten."}],
            "revision_edits": [{"revision_id": 9}],
        }

        with patch.object(ai_processor, "_get_class_commentary_client", return_value=client):
            payload, usage = ai_processor.generate_class_commentary_skill_candidate(
                candidate_input=frozen_input,
                provider="openai",
                model="memory-model",
                include_usage=True,
            )

        self.assertEqual(payload["incorporated_memory_record_ids"], [7])
        self.assertEqual(json.loads(captured["messages"][1]["content"]), frozen_input)
        self.assertEqual(captured["temperature"], 0)
        self.assertEqual(captured["response_format"], {"type": "json_object"})
        self.assertEqual(usage["input_tokens"], 12)
        self.assertIn("Never add student names", captured["messages"][0]["content"])
        self.assertIn("Use all supplied frozen revision diffs", captured["messages"][0]["content"])
        self.assertIn("may be empty", captured["messages"][0]["content"])

    def test_skill_replay_evaluator_uses_structured_json(self):
        captured = {}
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=lambda **kwargs: captured.update(kwargs) or _response(
                        {
                            "candidate_skill_student_fact_count": 0,
                            "samples": [
                                {
                                    "task_id": 1,
                                    "revision_id": 2,
                                    "base_roster_consistent": True,
                                    "candidate_roster_consistent": True,
                                    "base_unsupported_fact_count": 1,
                                    "candidate_unsupported_fact_count": 0,
                                    "base_plain_text_valid": True,
                                    "candidate_plain_text_valid": True,
                                    "base_structure_valid": False,
                                    "candidate_structure_valid": True,
                                    "candidate_style_memory_record_ids": [7],
                                }
                            ]
                        }
                    )
                )
            )
        )
        evaluation_input = {
            "style_rules": [{"memory_record_id": 7}],
            "samples": [{"task_id": 1, "revision_id": 2}],
        }

        with patch.object(ai_processor, "_get_class_commentary_client", return_value=client):
            payload = ai_processor.evaluate_class_commentary_skill_candidate_replays(
                evaluation_input=evaluation_input,
                provider="openai",
                model="memory-model",
            )

        self.assertEqual(payload["candidate_skill_student_fact_count"], 0)
        self.assertEqual(payload["samples"][0]["candidate_unsupported_fact_count"], 0)
        self.assertEqual(json.loads(captured["messages"][1]["content"]), evaluation_input)
        self.assertEqual(captured["temperature"], 0)
        self.assertEqual(captured["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
