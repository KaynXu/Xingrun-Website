import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
import app as app_module
from review_plan_workflow.llm import PromptRegistry, render_prompt
from review_plan_workflow.quality_gate import review_single_lesson_plan
from review_plan_workflow.service import generate_single_lesson_review_plan
from tests.review_plan_test_utils import valid_single_lesson_plan


class ReviewPlanWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prompt_registry_loads_subject_pack_and_versions_paths(self):
        registry = PromptRegistry()
        physics_pack = registry.read_yaml("subjects/physics.yaml")
        self.assertEqual(physics_pack["subject"], "physics")
        rendered = render_prompt(
            system_prompt_path="system/review-plan-agent.md",
            node_prompt_path="nodes/quality-reviewer.md",
            subject_pack_path="subjects/physics.yaml",
            rubric_path="rubrics/review-plan-quality.yaml",
            variables={"trace_id": "trace-1"},
            registry=registry,
        )
        self.assertIn("专业的复习计划生成 Agent", rendered["prompt"])
        self.assertIn("中国小学、初中、高中课程与考试复习", rendered["prompt"])
        self.assertIn("不要默认套用国际课程", rendered["prompt"])
        self.assertIn("formula", rendered["prompt"])
        self.assertRegex(rendered["prompt_version"], r"^[0-9a-f]{12}$")

    def test_quality_gate_flags_invalid_single_lesson_shape(self):
        review = review_single_lesson_plan({"lesson_info": {"topic": "一次函数"}, "days": []}, subject="math")
        self.assertFalse(review.passed)
        self.assertTrue(review.must_revise)
        self.assertTrue(any(issue.category == "schema" for issue in review.issues))

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_service_records_trace_run_without_mutating_plan_json(self, mock_generate_plan):
        plan = valid_single_lesson_plan(subject="物理", topic="电路")
        usage = {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "input_tokens": 10,
            "output_tokens": 20,
        }
        mock_generate_plan.return_value = (plan, usage)
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-01",
            subject="物理",
            grade="初三",
            topic="电路",
            summary="课堂总结文本",
            weak_points="单位和实验",
        )

        generated, generated_usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="物理",
            grade="初三",
            topic="电路",
            weak_points="单位和实验",
            lesson_date="2026-06-01",
            provider="deepseek",
            model="deepseek-v4-pro",
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        self.assertEqual(generated, plan)
        self.assertEqual(generated_usage, usage)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["style_version"], "physics-master-style.v1")
        self.assertIn("quality_reviewer", run["node_outputs"])
        self.assertIn("plan_generator", run["node_outputs"])
        self.assertIn("scope_planner", run["node_outputs"])
        self.assertIn("time_allocator", run["node_outputs"])
        self.assertIn("task_blueprint", run["node_outputs"])
        self.assertIn("prompt_bundle_builder", run["node_outputs"])
        self.assertEqual(run["node_outputs"]["task_blueprint"]["subject"], "physics")
        self.assertIn("formula_sheet", run["node_outputs"]["task_blueprint"]["required_components"])
        self.assertEqual(run["node_outputs"]["time_allocator"]["review_schedule"][0]["day"], 1)
        self.assertIn("中国小学、初中、高中课程与考试复习", run["node_outputs"]["prompt_bundle_builder"]["prompt_preview"])

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_service_uses_review_plan_model_override_when_provider_omitted(self, mock_generate_plan):
        config_runtime.write_file_config({
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-4.1",
        })
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        mock_generate_plan.return_value = (
            plan,
            {"provider": "openai", "model": "gpt-4.1", "input_tokens": 10, "output_tokens": 20},
        )
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-01",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本",
            weak_points="斜率判断",
        )

        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="初二",
            topic="一次函数",
            weak_points="斜率判断",
            lesson_date="2026-06-01",
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        self.assertEqual(generated, plan)
        self.assertEqual(usage["model"], "gpt-4.1")
        mock_generate_plan.assert_called_once()
        self.assertEqual(mock_generate_plan.call_args.kwargs["provider"], "openai")
        self.assertEqual(mock_generate_plan.call_args.kwargs["model"], "gpt-4.1")
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["provider"], "openai")
        self.assertEqual(run["model"], "gpt-4.1")

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_plan_generator_repairs_invalid_schema_once(self, mock_generate_plan):
        valid_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        mock_generate_plan.side_effect = [
            ({"lesson_info": {"topic": "一次函数"}, "days": []}, {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 3, "output_tokens": 4}),
            (valid_plan, {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 5, "output_tokens": 6}),
        ]

        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="初二",
            topic="一次函数",
            weak_points="斜率判断",
            lesson_date="2026-06-01",
            provider="deepseek",
            model="deepseek-v4-pro",
            include_usage=True,
        )

        self.assertEqual(generated, valid_plan)
        self.assertEqual(usage["input_tokens"], 8)
        self.assertEqual(usage["output_tokens"], 10)
        self.assertEqual(mock_generate_plan.call_count, 2)

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_plan_generator_repairs_json_parse_failure_once(self, mock_generate_plan):
        valid_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        mock_generate_plan.side_effect = [
            ValueError("bad json"),
            (valid_plan, {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 5, "output_tokens": 6}),
        ]

        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="初二",
            topic="一次函数",
            weak_points="斜率判断",
            lesson_date="2026-06-01",
            provider="deepseek",
            model="deepseek-v4-pro",
            include_usage=True,
        )

        self.assertEqual(generated, valid_plan)
        self.assertEqual(usage["input_tokens"], 5)
        self.assertEqual(usage["output_tokens"], 6)
        self.assertEqual(mock_generate_plan.call_count, 2)

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_service_revises_low_quality_plan_until_quality_passes(self, mock_generate_plan, mock_revise_plan):
        low_quality_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        low_quality_plan["weak_points_summary"] = "（具体题目）"
        fixed_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        mock_generate_plan.return_value = (
            low_quality_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )
        mock_revise_plan.return_value = (
            fixed_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 30, "output_tokens": 40},
        )

        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="初二",
            topic="一次函数",
            weak_points="斜率判断",
            lesson_date="2026-06-01",
            provider="deepseek",
            model="deepseek-v4-pro",
            include_usage=True,
        )

        self.assertEqual(generated, fixed_plan)
        self.assertEqual(usage["input_tokens"], 40)
        self.assertEqual(usage["output_tokens"], 60)
        mock_revise_plan.assert_called_once()

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_service_returns_best_plan_with_warning_after_two_failed_revisions(self, mock_generate_plan, mock_revise_plan):
        low_quality_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        low_quality_plan["weak_points_summary"] = "（具体题目）"
        still_low_quality_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        still_low_quality_plan["weak_points_summary"] = "按实际填写"
        mock_generate_plan.return_value = (
            low_quality_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )
        mock_revise_plan.return_value = (
            still_low_quality_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 1, "output_tokens": 2},
        )

        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-01",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结文本",
            weak_points="斜率判断",
        )
        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
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

        self.assertEqual(generated, still_low_quality_plan)
        self.assertEqual(usage["input_tokens"], 12)
        self.assertEqual(usage["output_tokens"], 24)
        self.assertEqual(mock_revise_plan.call_count, 2)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["quality_review"]["passed"], False)
        self.assertTrue(any(warning["code"] == "quality_revision_required" for warning in run["warnings"]))

    def test_lesson_serialization_includes_latest_review_plan_run(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-01",
            subject="数学",
            grade="初三",
            topic="二次函数",
            summary="课堂总结文本",
            weak_points="最值",
        )
        lesson_manager.save_review_plan_run(
            lesson_id=lesson_id,
            organization_id=1,
            trace_id="trace-serialization",
            status="succeeded",
            subject="math",
            provider="deepseek",
            model="deepseek-v4-pro",
            prompt_version="prompt.v1",
            style_version="physics-master-style.v1",
            schema_version="schema.v1",
            warnings=[{"code": "demo", "message": "warning", "severity": "low"}],
            quality_review={"score": 88, "passed": True},
            node_outputs={"quality_reviewer": {"score": 88}},
            logs=[{"node_name": "quality_reviewer", "status": "success", "latency_ms": 1}],
        )

        serialized = app_module._serialize_lesson_for_response(lesson_manager.get_lesson(lesson_id))

        self.assertEqual(serialized["trace_id"], "trace-serialization")
        self.assertEqual(serialized["workflow_warnings"][0]["code"], "demo")
        self.assertEqual(serialized["quality_review"]["score"], 88)
        self.assertEqual(serialized["style_version"], "physics-master-style.v1")


if __name__ == "__main__":
    unittest.main()
