import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
from review_plan_workflow import observability
from review_plan_workflow.llm import client as llm_client_module
from review_plan_workflow.service import generate_single_lesson_review_plan
from review_plan_workflow.source_brief import source_text_hash
from tests.review_plan_test_utils import valid_single_lesson_plan


class FakeLangfuseObservation:
    def __init__(self, client, kwargs):
        self.client = client
        self.kwargs = kwargs
        self.updates = []

    def __enter__(self):
        self.client.active.append(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.client.active:
            self.client.active.pop()
        return False

    def update(self, **kwargs):
        self.updates.append(kwargs)


class FakeLangfuseClient:
    def __init__(self):
        self.started = []
        self.observations = []
        self.current_updates = []
        self.scores = []
        self.active = []
        self.flush_count = 0

    def start_as_current_observation(self, **kwargs):
        self.started.append(kwargs)
        observation = FakeLangfuseObservation(self, kwargs)
        self.observations.append(observation)
        return observation

    def update_current_observation(self, **kwargs):
        self.current_updates.append(kwargs)
        if self.active:
            self.active[-1].update(**kwargs)

    def create_score(self, **kwargs):
        self.scores.append(kwargs)

    def flush(self):
        self.flush_count += 1


def fake_langfuse_module(fake_client):
    module = types.ModuleType("langfuse")
    module.get_client = lambda: fake_client
    return module


class ReviewPlanObservabilityTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        observability._LANGFUSE_CLIENT = None

    def tearDown(self):
        observability._LANGFUSE_CLIENT = None
        self.temp_dir.cleanup()

    def langfuse_env(self):
        return {
            "XR_REVIEW_PLAN_LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
        }

    def test_summarize_for_observability_keeps_source_brief_metrics_only(self):
        raw_source = "这段完整课堂材料不要进入 Langfuse。老师强调：先看固定量，再判断轨迹。"
        summary = observability.summarize_for_observability(
            {
                "source_brief": {
                    "schema_version": "2026-07-01",
                    "source_text_hash": source_text_hash(raw_source),
                    "cleaned_text": raw_source,
                    "lesson_title_candidates": ["动点与立体几何综合"],
                    "knowledge_points": [{"name": "空间轨迹"}],
                    "teacher_emphasis": [{"quote": "先看固定量，再判断轨迹"}],
                    "missing_fields": ["example_stems"],
                    "evidence_map": [{"quote": "这段完整课堂材料不要进入 Langfuse"}],
                    "confidence": 0.82,
                }
            }
        )

        blob = json.dumps(summary, ensure_ascii=False)
        self.assertIn(source_text_hash(raw_source), blob)
        self.assertIn("knowledge_points_count", blob)
        self.assertIn("teacher_emphasis_count", blob)
        self.assertIn("example_stems", blob)
        self.assertNotIn("cleaned_text", blob)
        self.assertNotIn('"quote"', blob)
        self.assertNotIn("这段完整课堂材料不要进入 Langfuse", blob)
        self.assertNotIn("先看固定量，再判断轨迹", blob)

    def test_langfuse_env_sets_host_alias_for_sdk_compatibility(self):
        fake_client = FakeLangfuseClient()
        with patch.dict(
            os.environ,
            {
                "XR_REVIEW_PLAN_LANGFUSE_ENABLED": "true",
                "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                "LANGFUSE_SECRET_KEY": "sk-lf-test",
                "LANGFUSE_BASE_URL": "https://us.cloud.langfuse.com",
            },
            clear=True,
        ), patch.dict(sys.modules, {"langfuse": fake_langfuse_module(fake_client)}):
            client = observability.get_langfuse_client()
            self.assertEqual(os.environ.get("LANGFUSE_BASE_URL"), "https://us.cloud.langfuse.com")
            self.assertEqual(os.environ.get("LANGFUSE_HOST"), "https://us.cloud.langfuse.com")

        self.assertIs(client, fake_client)

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_service_emits_langfuse_trace_without_full_classroom_text(self, mock_generate_plan):
        fake_client = FakeLangfuseClient()
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        usage = {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "input_tokens": 10,
            "output_tokens": 20,
        }
        mock_generate_plan.return_value = (plan, usage)
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-01",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本-不要进入Langfuse",
            weak_points="斜率判断",
        )

        with patch.dict(os.environ, self.langfuse_env(), clear=True), patch.dict(
            sys.modules,
            {"langfuse": fake_langfuse_module(fake_client)},
        ):
            generated, generated_usage = generate_single_lesson_review_plan(
                summary_text="课堂总结文本-不要进入Langfuse",
                subject="数学",
                grade="初二",
                topic="一次函数",
                weak_points="斜率判断",
                lesson_date="2026-06-01",
                provider="deepseek",
                model="deepseek-v4-pro",
                lesson_id=lesson_id,
                organization_id=1,
                include_usage=True,
            )

        self.assertEqual(generated["lesson_info"]["topic"], "一次函数")
        self.assertEqual(generated_usage, usage)
        started_names = [item["name"] for item in fake_client.started]
        self.assertEqual(started_names[0], "review_plan.workflow")
        self.assertIn("review_plan.node.plan_generator", started_names)
        self.assertTrue(fake_client.scores)
        self.assertEqual(fake_client.scores[0]["name"], "review_plan_quality")
        self.assertEqual(fake_client.flush_count, 1)

        telemetry_blob = json.dumps(
            {
                "started": fake_client.started,
                "updates": [observation.updates for observation in fake_client.observations],
                "current_updates": fake_client.current_updates,
            },
            ensure_ascii=False,
        )
        self.assertNotIn("课堂总结文本-不要进入Langfuse", telemetry_blob)
        self.assertIn("sha256", telemetry_blob)

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_langfuse_trace_includes_source_metrics_without_source_text(self, mock_generate_plan):
        fake_client = FakeLangfuseClient()
        raw_source = (
            "本节课主题：动点与立体几何综合\n"
            "知识点：空间轨迹与固定量。\n"
            "老师强调：先看固定量，再判断轨迹。\n"
            "例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？\n"
            "这段完整课堂材料不要进入 Langfuse。"
        )
        mock_generate_plan.return_value = (
            valid_single_lesson_plan(subject="数学", topic="动点与立体几何综合"),
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )

        with patch.dict(os.environ, self.langfuse_env(), clear=True), patch.dict(
            sys.modules,
            {"langfuse": fake_langfuse_module(fake_client)},
        ):
            generate_single_lesson_review_plan(
                summary_text=raw_source,
                subject="数学",
                grade="六年级",
                topic="动点与立体几何综合",
                lesson_date="2026-07-01",
                provider="deepseek",
                model="deepseek-v4-pro",
            )

        telemetry_blob = json.dumps(
            {
                "started": fake_client.started,
                "updates": [observation.updates for observation in fake_client.observations],
                "current_updates": fake_client.current_updates,
            },
            ensure_ascii=False,
        )
        self.assertIn("source_brief", telemetry_blob)
        self.assertIn(source_text_hash(raw_source), telemetry_blob)
        self.assertIn("knowledge_points_count", telemetry_blob)
        self.assertIn("teacher_emphasis_count", telemetry_blob)
        self.assertIn("confidence", telemetry_blob)
        self.assertNotIn("cleaned_text", telemetry_blob)
        self.assertNotIn('"quote"', telemetry_blob)
        self.assertNotIn("课堂材料摘录", telemetry_blob)
        self.assertNotIn("已校验工作流上下文", telemetry_blob)
        self.assertNotIn("这段完整课堂材料不要进入 Langfuse", telemetry_blob)
        self.assertNotIn("先看固定量，再判断轨迹", telemetry_blob)

    def test_llm_generation_span_summarizes_prompt_and_user_message(self):
        fake_client = FakeLangfuseClient()
        response = type(
            "Response",
            (),
            {
                "choices": [type("Choice", (), {"message": type("Message", (), {"content": "{\"ok\": true}"})()})()],
                "usage": type("Usage", (), {"prompt_tokens": 11, "completion_tokens": 22})(),
                "model": "deepseek-v4-pro",
            },
        )()
        create_mock = unittest.mock.Mock(return_value=response)
        fake_openai_client = type(
            "Client",
            (),
            {
                "chat": type(
                    "Chat",
                    (),
                    {"completions": type("Completions", (), {"create": create_mock})()},
                )()
            },
        )()

        with patch.dict(os.environ, self.langfuse_env(), clear=True), patch.dict(
            sys.modules,
            {"langfuse": fake_langfuse_module(fake_client)},
        ), patch.object(llm_client_module, "get_chat_client", return_value=fake_openai_client):
            payload, usage = llm_client_module.generate_review_plan_json(
                system_prompt="系统提示词-不要进入Langfuse",
                user_message="课堂总结全文-不要进入Langfuse",
                provider="deepseek",
                model="deepseek-v4-pro",
            )

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(usage["input_tokens"], 11)
        generation_start = next(item for item in fake_client.started if item["name"] == "review_plan.llm.generate_json")
        generation_blob = json.dumps(generation_start, ensure_ascii=False)
        self.assertNotIn("系统提示词-不要进入Langfuse", generation_blob)
        self.assertNotIn("课堂总结全文-不要进入Langfuse", generation_blob)
        self.assertIn("sha256", generation_blob)


if __name__ == "__main__":
    unittest.main()
