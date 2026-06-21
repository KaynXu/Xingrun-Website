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
from review_plan_workflow.llm import client as llm_client_module
from review_plan_workflow.llm import PromptRegistry, render_prompt
from review_plan_workflow.quality_gate import review_single_lesson_plan
from review_plan_workflow.schemas import validate_final_review_plan
from review_plan_workflow.service import generate_single_lesson_review_plan
from tests.review_plan_test_utils import (
    components_only_single_lesson_plan,
    desktop_writer_single_lesson_plan,
    valid_single_lesson_plan,
    writer_style_single_lesson_plan,
)


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

    def test_rendered_generation_prompt_includes_migrated_desktop_rules(self):
        registry = PromptRegistry()
        common_kwargs = {
            "system_prompt_path": "system/review-plan-agent.md",
            "node_prompt_path": "nodes/task-generator.md",
            "style_path": "styles/review_plan_style.yaml",
            "rubric_path": "rubrics/review-plan-quality.yaml",
            "variables": {"trace_id": "trace-1"},
            "registry": registry,
        }

        math_prompt = render_prompt(subject_pack_path="subjects/math.yaml", **common_kwargs)["prompt"]
        physics_prompt = render_prompt(subject_pack_path="subjects/physics.yaml", **common_kwargs)["prompt"]
        ielts_prompt = render_prompt(subject_pack_path="subjects/ielts.yaml", **common_kwargs)["prompt"]

        self.assertIn("不能把作业布置设置成题目本身", math_prompt)
        self.assertIn("不把“方法、入口、边界、条件、过程、动作、提醒”等抽象词作为主要设空答案", math_prompt)
        self.assertIn("老师追问卡片必须有完整题干或同类题背景", math_prompt)
        self.assertIn("禁止只写 `A`、`B`、`C`、`D`", math_prompt)
        self.assertIn("第14天和第30天只回收第1/2/7天内容", physics_prompt)
        self.assertIn("公式 + 物理量含义 + 常用单位 + 适用条件", physics_prompt)
        self.assertIn("物理里的远方", physics_prompt)
        self.assertIn("背景公式必须优先使用当堂课公式", physics_prompt)
        self.assertIn("雅思阅读复习不是背文章内容", ielts_prompt)
        self.assertIn("False、Not Given", ielts_prompt)
        self.assertIn("词汇、定位、逻辑三类归因", ielts_prompt)
        self.assertIn("full_review_topics` 是首页“全课覆盖清单”，必须输出 5-10 条颗粒化条目", math_prompt)
        self.assertIn("JSON 字符串中的 LaTeX 反斜杠必须转义", math_prompt)
        self.assertIn("禁止把使用说明、完成标准、正确率要求、系统兜底句写进 `quotes`", math_prompt)

    def test_quality_gate_flags_invalid_single_lesson_shape(self):
        review = review_single_lesson_plan({"lesson_info": {"topic": "一次函数"}, "days": []}, subject="math")
        self.assertFalse(review.passed)
        self.assertTrue(review.must_revise)
        self.assertTrue(any(issue.category == "schema" for issue in review.issues))

    def test_validate_final_review_plan_accepts_writer_style_day_shape(self):
        plan, errors = validate_final_review_plan(writer_style_single_lesson_plan())
        self.assertIsNotNone(plan)
        self.assertEqual(errors, [])

    def test_validate_final_review_plan_accepts_desktop_writer_shape(self):
        plan, errors = validate_final_review_plan(desktop_writer_single_lesson_plan())
        self.assertIsNotNone(plan)
        self.assertEqual(errors, [])
        self.assertEqual(plan.lesson_info.topic, "二次函数最值与将军饮马综合复习")
        self.assertEqual(plan.lesson_info.grade, "9")
        self.assertEqual([day.day for day in plan.days], [1, 2, 7, 14, 30])

    def test_validate_final_review_plan_normalizes_components_only_writer_shape(self):
        plan, errors = validate_final_review_plan(components_only_single_lesson_plan())
        self.assertIsNotNone(plan)
        self.assertEqual(errors, [])
        self.assertEqual(plan.lesson_info.topic, "不等式与函数复习")
        self.assertEqual(plan.weak_points_summary, "每次复习包含填空、选择、口述卡片三个板块。")
        self.assertIn("不等式与函数复习", plan.full_review_topics)
        self.assertEqual(plan.days[0].blanks[0]["text"], "已知 x>0,y>0，且 1/x+2/y=1，则 x+2y 的最小值是______。")
        self.assertEqual(plan.days[0].choices[0]["question"], "下列函数中，与 f(x)=(x²-1)/(x-1) 相等的是（ ）。")
        self.assertIn("解函数不等式时，第一步先判断", plan.days[0].items[-1]["text"])

    def test_validate_final_review_plan_normalizes_wrapped_camel_case_writer_shape(self):
        wrapped_plan = {
            "reviewPlan": {
                "subject": "数学",
                "grade": "高一",
                "topic": "不等式与函数复习",
                "lessonDate": "2026-06-16",
                "generatedDate": "2026-06-18",
                "days": [
                    {
                        "day": day,
                        "date": f"2026-06-{18 + index:02d}",
                        "reviewGoal": "复现定义域与函数不等式的关键步骤。",
                        "focus": "定义域、单调性、同解转化。",
                        "fillInBlanks": [
                            {
                                "question": f"第{day}天：解 f(2x+1)>f(x-2) 前必须检查两个括号都落在 ________ 内。",
                                "answer": "定义域",
                            }
                        ],
                        "multipleChoice": [
                            {
                                "question": f"第{day}天：下列哪一步最能避免定义域遗漏？",
                                "options": [
                                    "A. 先列内层范围限制",
                                    "B. 只比较两个括号大小",
                                    "C. 先猜答案再代入",
                                    "D. 忽略函数是否单调",
                                ],
                                "answer": "A",
                            }
                        ],
                        "activeRecall": {
                            "type": "methodRecall",
                            "content": ["函数不等式先看 ________，再看定义域限制。"],
                            "answers": ["单调性"],
                        },
                        "completionCriteria": "能独立写出定义域限制并完成同解转化。",
                    }
                    for index, day in enumerate([1, 2, 7, 14, 30])
                ],
            },
            "days": [],
            "weak_points_summary": "计算能力弱，易忽略定义域",
        }

        plan, errors = validate_final_review_plan(wrapped_plan)

        self.assertIsNotNone(plan)
        self.assertEqual(errors, [])
        self.assertEqual(plan.lesson_info.topic, "不等式与函数复习")
        self.assertEqual(plan.lesson_info.date, "2026-06-16")
        self.assertEqual([day.day for day in plan.days], [1, 2, 7, 14, 30])
        self.assertEqual(plan.days[0].goal, "复现定义域与函数不等式的关键步骤。")
        self.assertEqual(plan.days[0].blanks[0]["answer"], "定义域")
        self.assertEqual(plan.days[0].choices[0]["options"][0], "A. 先列内层范围限制")
        self.assertIn("函数不等式先看", plan.days[0].items[-1]["text"])

    def test_quality_gate_uses_normalized_day_numbers(self):
        review = review_single_lesson_plan(desktop_writer_single_lesson_plan(), subject="math")
        self.assertTrue(review.passed)
        self.assertFalse(any(issue.category in {"schema", "completeness"} for issue in review.issues))

    def test_quality_gate_rejects_pdf_fallback_content(self):
        broken_plan = valid_single_lesson_plan(subject="数学", topic="课后")
        broken_plan["lesson_info"]["topic"] = ""
        broken_plan["full_review_topics"] = []
        broken_plan["weak_points_summary"] = ""
        for day in broken_plan["days"]:
            day["steps"] = []
            day["items"] = []
            day["blanks"] = []
            day["choices"] = []
            day["goal"] = ""
            day["focus"] = ""
            day["self_test_phrase"] = "请完成以上填空和选择题，并对照答案自检。"

        review = review_single_lesson_plan(broken_plan, subject="math")

        self.assertFalse(review.passed)
        self.assertTrue(review.must_revise)
        self.assertTrue(any(issue.category == "pdf_readiness" for issue in review.issues))

    def test_quality_gate_accepts_components_only_writer_shape_after_normalization(self):
        review = review_single_lesson_plan(components_only_single_lesson_plan(), subject="math")

        self.assertTrue(review.passed, review.model_dump())
        self.assertFalse(any(issue.category == "pdf_readiness" for issue in review.issues))

    def test_quality_gate_rejects_generic_coverage_instruction_quote_and_bad_math_text(self):
        plan = valid_single_lesson_plan(subject="数学", topic="不等式与函数复习")
        plan["full_review_topics"] = ["不等式与函数复习"]
        plan["lesson_info"]["key_categories"] = []
        plan["quotes"] = ["每一个复习日都要完整复习整节课内容。"]
        plan["days"][0]["blanks"] = [
            {
                "text": "已知 f(x)=begincases 2\\x00, & x≤0 log_(2)x, & x>0 endcases，则定义域为______。",
                "answer": "x≤0 或 x>0",
            }
        ]

        review = review_single_lesson_plan(plan, subject="math")

        self.assertFalse(review.passed)
        self.assertTrue(review.must_revise)
        descriptions = "\n".join(issue.description for issue in review.issues)
        fixes = "\n".join(review.revision_instructions)
        self.assertIn("全课覆盖清单", descriptions)
        self.assertIn("课堂金句", descriptions)
        self.assertIn("公式", descriptions)
        self.assertIn("5-10", fixes)
        self.assertIn("quotes 留空", fixes)
        self.assertIn("$...$", fixes)

    def test_quality_gate_rejects_sparse_duplicate_unique_question_content(self):
        plan = valid_single_lesson_plan(subject="数学", topic="不等式与函数复习")
        plan["full_review_topics"] = [
            "全方和不等式",
            "柯西不等式",
            "抽象函数定义域",
            "同一函数辨析",
            "函数不等式同解转化",
        ]
        for day in plan["days"]:
            day["blanks"] = [
                {"text": "同一函数判断先比较_______。", "answer": "定义域"},
            ]
            day["items"] = [
                {"type": "fill", "text": "同一函数判断先比较_______。", "answer": "定义域"},
                {"type": "fill", "text": "同一函数判断先比较_______。", "answer": "定义域"},
            ]
            day["choices"] = [
                {
                    "question": "抽象函数定义域先看什么？",
                    "options": ["A. 括号整体", "B. 字体", "C. 页码", "D. 颜色"],
                    "answer": "A",
                }
            ]

        review = review_single_lesson_plan(plan, subject="math")

        self.assertFalse(review.passed)
        self.assertTrue(review.must_revise)
        self.assertTrue(any("唯一可打印题目" in issue.description for issue in review.issues))

    def test_quality_gate_rejects_skeletal_choice_options(self):
        plan = valid_single_lesson_plan(subject="数学", topic="不等式与函数复习")
        for day in plan["days"]:
            day["choices"] = [
                {
                    "question": "已知 f(x) 为增函数，则 f(1-x²)<f(2x) 的关键转化是（ ）",
                    "options": ["A", "B", "C", "D"],
                    "answer": "A",
                }
            ]

        review = review_single_lesson_plan(plan, subject="math")

        self.assertFalse(review.passed)
        self.assertTrue(review.must_revise)
        self.assertTrue(any("空壳" in issue.description for issue in review.issues))

    def test_generate_review_plan_json_sets_timeout(self):
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
        fake_client = type(
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
        with patch.object(llm_client_module, "get_chat_client", return_value=fake_client):
            payload, usage = llm_client_module.generate_review_plan_json(
                system_prompt="system",
                user_message="user",
                provider="deepseek",
                model="deepseek-v4-pro",
                temperature=0.17,
                stage="unit_test_stage",
            )

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(usage["input_tokens"], 11)
        self.assertEqual(usage["output_tokens"], 22)
        self.assertEqual(create_mock.call_args.kwargs["timeout"], llm_client_module.REVIEW_PLAN_LLM_TIMEOUT_SECONDS)
        self.assertEqual(create_mock.call_args.kwargs["temperature"], 0.17)

    def test_generate_review_plan_json_passes_openai_reasoning_effort(self):
        response = type(
            "Response",
            (),
            {
                "choices": [type("Choice", (), {"message": type("Message", (), {"content": "{\"ok\": true}"})()})()],
                "usage": type("Usage", (), {"prompt_tokens": 3, "completion_tokens": 4})(),
                "model": "gpt-5.4",
            },
        )()
        create_mock = unittest.mock.Mock(return_value=response)
        fake_client = type(
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
        with patch.object(llm_client_module, "get_chat_client", return_value=fake_client):
            payload, usage = llm_client_module.generate_review_plan_json(
                system_prompt="system",
                user_message="user",
                provider="openai",
                model="gpt-5.4",
                reasoning_effort="high",
            )

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(usage["model"], "gpt-5.4")
        self.assertEqual(create_mock.call_args.kwargs["reasoning_effort"], "high")

    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_service_runs_parent_planner_writer_and_llm_reviewer(self, mock_parent_plan, mock_generate_plan, mock_llm_review):
        config_runtime.write_file_config({
            "openai_api_key": "test-openai",
            "deepseek_api_key": "test-deepseek",
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-5.4",
            "review_plan_reasoning_effort": "high",
            "review_plan_temperature": 0.21,
            "review_plan_writer_temperature": 0.36,
            "review_plan_reviewer_temperature": 0.08,
        })
        mock_parent_plan.return_value = (
            {
                "strategy_summary": "先拆定义域，再做函数不等式同解转化。",
                "student_diagnosis": ["忽略定义域"],
                "knowledge_map": [{"name": "定义域", "role": "函数不等式前置条件", "evidence": "课堂主题"}],
                "day_strategies": [
                    {
                        "day": day,
                        "objective": "复现定义域检查",
                        "retrieval_focus": ["定义域", "单调性"],
                        "question_design": ["填空题检查定义域"],
                        "review_loop": ["错因复盘"],
                        "risk_controls": ["不要只写看条件"],
                    }
                    for day in [1, 2, 7, 14, 30]
                ],
                "writer_instructions": ["每天都要绑定定义域遗漏这个错因。"],
                "quality_risks": ["题目可能结构完整但不可做。"],
                "success_criteria": ["每道题可独立作答。"],
                "assumptions": [],
                "confidence": 0.86,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 100, "output_tokens": 40},
        )
        plan = valid_single_lesson_plan(subject="数学", topic="不等式与函数复习")
        mock_generate_plan.return_value = (
            plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 200, "output_tokens": 80},
        )
        mock_llm_review.return_value = (
            {"score": 96, "passed": True, "must_revise": False, "issues": [], "revision_instructions": []},
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 120, "output_tokens": 20},
        )
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-18",
            subject="数学",
            grade="高一",
            topic="不等式与函数复习",
            summary="课堂总结文本",
            weak_points="忽略定义域",
        )

        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="高一",
            topic="不等式与函数复习",
            weak_points="忽略定义域",
            lesson_date="2026-06-18",
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        self.assertEqual(generated["lesson_info"]["topic"], "不等式与函数复习")
        self.assertEqual(usage["input_tokens"], 420)
        self.assertEqual(usage["output_tokens"], 140)
        parent_kwargs = mock_parent_plan.call_args.kwargs
        self.assertEqual(parent_kwargs["provider"], "openai")
        self.assertEqual(parent_kwargs["model"], "gpt-5.4")
        self.assertEqual(parent_kwargs["reasoning_effort"], "high")
        self.assertEqual(parent_kwargs["temperature"], 0.21)
        self.assertEqual(parent_kwargs["stage"], "parent_planner")
        writer_kwargs = mock_generate_plan.call_args.kwargs
        self.assertEqual(writer_kwargs["provider"], "deepseek")
        self.assertEqual(writer_kwargs["model"], "deepseek-v4-pro")
        self.assertEqual(writer_kwargs["temperature"], 0.36)
        self.assertEqual(writer_kwargs["stage"], "plan_generator")
        self.assertIn("父模型教学蓝图", writer_kwargs["user_message"])
        self.assertIn("定义域", writer_kwargs["user_message"])
        reviewer_kwargs = mock_llm_review.call_args.kwargs
        self.assertEqual(reviewer_kwargs["provider"], "openai")
        self.assertEqual(reviewer_kwargs["temperature"], 0.08)
        self.assertEqual(reviewer_kwargs["stage"], "quality_reviewer_llm")
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertIn("parent_planner", run["node_outputs"])
        self.assertIn("quality_reviewer_llm", run["node_outputs"])
        self.assertEqual(run["node_outputs"]["plan_generator_model_config"]["temperature"], 0.36)

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_llm_reviewer_can_trigger_targeted_revision(
        self,
        mock_parent_plan,
        mock_generate_plan,
        mock_llm_review,
        mock_revise_plan,
    ):
        config_runtime.write_file_config({
            "openai_api_key": "test-openai",
            "deepseek_api_key": "test-deepseek",
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-5.4",
            "review_plan_reasoning_effort": "high",
            "review_plan_temperature": 0.22,
            "review_plan_writer_temperature": 0.37,
            "review_plan_reviewer_temperature": 0.09,
        })
        mock_parent_plan.return_value = (
            {
                "strategy_summary": "围绕定义域遗漏做定向复习。",
                "student_diagnosis": ["定义域遗漏"],
                "knowledge_map": [{"name": "定义域", "role": "函数题前置检查", "evidence": "课堂"}],
                "day_strategies": [
                    {"day": day, "objective": "定义域检查", "retrieval_focus": ["定义域"]}
                    for day in [1, 2, 7, 14, 30]
                ],
                "writer_instructions": ["修订时不要脱离定义域遗漏。"],
                "quality_risks": ["选择题可能只是结构完整。"],
                "success_criteria": ["题目必须可独立作答。"],
                "assumptions": [],
                "confidence": 0.84,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 10, "output_tokens": 5},
        )
        initial_plan = valid_single_lesson_plan(subject="数学", topic="不等式与函数复习")
        revised_plan = valid_single_lesson_plan(subject="数学", topic="不等式与函数复习")
        revised_plan["weak_points_summary"] = "已围绕定义域遗漏重写题目。"
        mock_generate_plan.return_value = (
            initial_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 20, "output_tokens": 10},
        )
        mock_llm_review.side_effect = [
            (
                {
                    "score": 70,
                    "passed": False,
                    "must_revise": True,
                    "issues": [
                        {
                            "severity": "high",
                            "category": "question_quality",
                            "description": "第1天选择题结构完整但没有检查定义域遗漏。",
                            "suggested_fix": "重写第1天选择题，绑定定义域遗漏错因。",
                        }
                    ],
                    "revision_instructions": ["只重写第1天选择题和主动回忆。"],
                },
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 8, "output_tokens": 4},
            ),
            (
                {"score": 92, "passed": True, "must_revise": False, "issues": [], "revision_instructions": []},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 7, "output_tokens": 3},
            ),
        ]
        mock_revise_plan.return_value = (
            revised_plan,
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 30, "output_tokens": 12},
        )

        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="高一",
            topic="不等式与函数复习",
            weak_points="定义域遗漏",
            lesson_date="2026-06-18",
            include_usage=True,
        )

        self.assertEqual(generated["weak_points_summary"], "已围绕定义域遗漏重写题目。")
        self.assertEqual(mock_revise_plan.call_count, 1)
        revise_kwargs = mock_revise_plan.call_args.kwargs
        self.assertEqual(revise_kwargs["stage"], "targeted_revision")
        self.assertEqual(revise_kwargs["temperature"], 0.22)
        self.assertIn("父模型教学蓝图", revise_kwargs["user_message"])
        self.assertIn("定义域遗漏", revise_kwargs["user_message"])
        self.assertEqual(usage["input_tokens"], 75)
        self.assertEqual(usage["output_tokens"], 34)

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

        self.assertEqual(generated["lesson_info"]["topic"], "电路")
        self.assertEqual(generated["lesson_info"]["date"], "2026-06-01")
        self.assertEqual(generated["weak_points_summary"], plan["weak_points_summary"])
        self.assertEqual(validate_final_review_plan(generated)[1], [])
        self.assertEqual(generated_usage, usage)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["style_version"], "physics-master-style.v2")
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
    def test_plan_generator_uses_writer_model_when_chain_model_differs(self, mock_generate_plan):
        config_runtime.write_file_config({
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-4.1",
        })
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        mock_generate_plan.return_value = (
            plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
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

        self.assertEqual(generated["lesson_info"]["topic"], "一次函数")
        self.assertEqual(generated["lesson_info"]["date"], "2026-06-01")
        self.assertEqual(validate_final_review_plan(generated)[1], [])
        self.assertEqual(usage["model"], "deepseek-v4-pro")
        mock_generate_plan.assert_called_once()
        self.assertEqual(mock_generate_plan.call_args.kwargs["provider"], "deepseek")
        self.assertEqual(mock_generate_plan.call_args.kwargs["model"], "deepseek-v4-pro")
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["provider"], "openai")
        self.assertEqual(run["model"], "gpt-4.1")
        self.assertEqual(run["node_outputs"]["plan_generator_model_config"]["provider"], "deepseek")
        self.assertEqual(run["node_outputs"]["plan_generator_model_config"]["model"], "deepseek-v4-pro")

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

        self.assertEqual(generated["lesson_info"]["topic"], "一次函数")
        self.assertEqual(generated["lesson_info"]["date"], "2026-06-01")
        self.assertEqual(validate_final_review_plan(generated)[1], [])
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

        self.assertEqual(generated["lesson_info"]["topic"], "一次函数")
        self.assertEqual(generated["lesson_info"]["date"], "2026-06-01")
        self.assertEqual(validate_final_review_plan(generated)[1], [])
        self.assertEqual(usage["input_tokens"], 5)
        self.assertEqual(usage["output_tokens"], 6)
        self.assertEqual(mock_generate_plan.call_count, 2)

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_plan_generator_normalizes_writer_style_output_without_schema_warning(self, mock_generate_plan):
        mock_generate_plan.return_value = (
            writer_style_single_lesson_plan(),
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )

        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-14",
            subject="数学",
            grade="九年级",
            topic="分式方程入门",
            summary="课堂总结文本",
            weak_points="基础计算、步骤表达",
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="九年级",
            topic="分式方程入门",
            weak_points="基础计算、步骤表达",
            lesson_date="2026-06-14",
            provider="deepseek",
            model="deepseek-v4-pro",
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        self.assertEqual(generated["weak_points_summary"], "基础计算；步骤表达")
        self.assertEqual(generated["days"][0]["items"][0]["text"], "回顾分式方程的定义、去分母和增根检验。")
        self.assertEqual(generated["days"][0]["choices"][0]["question"], "下列哪一步最容易产生增根？")
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["warnings"], [])
        self.assertTrue(run["quality_review"]["passed"])

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_plan_generator_normalizes_desktop_writer_output_without_schema_warning(self, mock_generate_plan):
        mock_generate_plan.return_value = (
            desktop_writer_single_lesson_plan(),
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )

        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-15",
            subject="数学",
            grade="九年级",
            topic="二次函数最值与将军饮马综合复习",
            summary="课堂总结文本",
            weak_points="表示线段、将军饮马入口",
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="九年级",
            topic="二次函数最值与将军饮马综合复习",
            weak_points="表示线段、将军饮马入口",
            lesson_date="2026-06-15",
            provider="deepseek",
            model="deepseek-v4-pro",
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        self.assertEqual(generated["lesson_info"]["topic"], "二次函数最值与将军饮马综合复习")
        self.assertEqual(generated["lesson_info"]["grade"], "9")
        self.assertEqual([day["day"] for day in generated["days"]], [1, 2, 7, 14, 30])
        self.assertEqual(
            generated["full_review_topics"],
            ["二次函数最值", "将军饮马最短路径", "上减下/右减左", "设参数表达坐标", "轴对称转化", "顶点公式求最值"],
        )
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["warnings"], [])
        self.assertTrue(run["quality_review"]["passed"])

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

        self.assertEqual(generated["lesson_info"]["topic"], fixed_plan["lesson_info"]["topic"])
        self.assertEqual(generated["lesson_info"]["date"], "2026-06-01")
        self.assertEqual(generated["weak_points_summary"], fixed_plan["weak_points_summary"])
        self.assertEqual([day["day"] for day in generated["days"]], [1, 2, 7, 14, 30])
        self.assertEqual(validate_final_review_plan(generated)[1], [])
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

        self.assertEqual(generated["lesson_info"]["topic"], still_low_quality_plan["lesson_info"]["topic"])
        self.assertEqual(generated["lesson_info"]["date"], "2026-06-01")
        self.assertEqual(generated["weak_points_summary"], still_low_quality_plan["weak_points_summary"])
        self.assertEqual([day["day"] for day in generated["days"]], [1, 2, 7, 14, 30])
        self.assertEqual(validate_final_review_plan(generated)[1], [])
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
            style_version="physics-master-style.v2",
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
        self.assertEqual(serialized["style_version"], "physics-master-style.v2")

    def test_new_running_review_plan_run_interrupts_previous_running_run(self):
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
            trace_id="trace-old",
            status="running",
        )
        lesson_manager.save_review_plan_run(
            lesson_id=lesson_id,
            organization_id=1,
            trace_id="trace-new",
            status="running",
        )

        with lesson_manager.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT trace_id, status
                FROM review_plan_runs
                WHERE lesson_id=?
                ORDER BY id
                """,
                (lesson_id,),
            ).fetchall()

        self.assertEqual(
            [(row["trace_id"], row["status"]) for row in rows],
            [("trace-old", "interrupted"), ("trace-new", "running")],
        )


if __name__ == "__main__":
    unittest.main()
