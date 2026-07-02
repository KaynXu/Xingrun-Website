import json
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
from review_plan_workflow.schemas import (
    QualityIssue,
    QualityReview,
    ReviewPlanInput,
    ReviewPlanSourceBrief,
    SourceSummary,
    TaskBlueprint,
    normalize_final_review_plan,
    validate_final_review_plan,
)
from review_plan_workflow.service import _fallback_agent_blueprint, generate_single_lesson_review_plan
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

    def test_normalizes_section_questions_for_compressed_day_quality_gate(self):
        plan = {
            "lesson_info": {"subject": "数学", "grade": "三年级", "date": "2026-07-01", "topic": "几何最短路径复习"},
            "full_review_topics": ["面积比转高的比例", "动点轨迹判断", "轴对称最短路径", "桥模型端点对应", "分段关系式"],
            "quotes": ["面积比不是直接给面积，而是告诉高的关系。"],
            "days": [
                {
                    "day_number": 1,
                    "date": "2026-07-02",
                    "objective": "用错因、步骤和模型复盘几何最短路径。",
                    "sections": [
                        {
                            "type": "mixed",
                            "title": "填空与选择诊断",
                            "instructions": "完成后标注错因。",
                            "questions": [
                                {
                                    "id": "blank1",
                                    "type": "blank",
                                    "question": "同底三角形面积比等于对应______的比。",
                                    "answer": ["高"],
                                },
                                {
                                    "id": "blank2",
                                    "type": "blank",
                                    "question": "点到直线的距离固定时，动点轨迹是一条与该直线______的直线。",
                                    "answer": "平行",
                                },
                                {
                                    "id": "blank3",
                                    "type": "blank",
                                    "question": "轴对称最短路径先作一个定点关于轨迹线的______。",
                                    "answer": "对称点",
                                },
                                {
                                    "id": "choice1",
                                    "type": "choice",
                                    "question": "求定点 A 到直线 l 上动点 P 再到定点 B 的最短路径，第一步通常是？",
                                    "options": ["A. 作 A 关于 l 的对称点", "B. 直接量 AP", "C. 随便取 P", "D. 先算面积"],
                                    "answer": "A",
                                },
                                {
                                    "id": "choice2",
                                    "type": "choice",
                                    "question": "动点面积图像写关系式时，最容易漏掉的是？",
                                    "options": ["A. 时间范围", "B. 图像颜色", "C. 题号", "D. 字体大小"],
                                    "answer": "A",
                                },
                            ],
                        }
                    ],
                    "completion_criteria": "能说清轨迹、变换、锁点、计算四步。",
                }
            ],
        }

        normalized = normalize_final_review_plan(plan)
        day = normalized["days"][0]
        self.assertEqual(len(day["blanks"]), 3)
        self.assertEqual(len(day["choices"]), 2)
        self.assertEqual(day["blanks"][0]["answer"], "高")

        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
        )
        self.assertTrue(review.passed, [issue.description for issue in review.issues])

    def test_normalization_keeps_blank_answer_aliases_without_duplicate_fill_items(self):
        plan = valid_single_lesson_plan(subject="数学", topic="二次函数")
        plan["days"] = [
            {
                "day": 1,
                "goal": "复盘二次函数图像与参数。",
                "items": [{"type": "body", "text": "先口述开口、对称轴、顶点三步。"}],
                "blanks": [
                    {"text": "二次函数图像开口由______决定。", "reference_answer": "a 的符号"},
                    {"text": "顶点式中顶点坐标是______。", "answers": ["(h, k)"]},
                    {"text": "对称轴公式是______。", "answer_hint": "$x=-b/(2a)$"},
                ],
                "choices": [
                    {
                        "question": "二次函数 y=ax²+bx+c 中，a>0 时图像开口方向是？",
                        "options": ["A. 向上", "B. 向下", "C. 向左", "D. 向右"],
                        "answer": "A",
                    },
                    {
                        "question": "判断最值前应先看什么？",
                        "options": ["A. 开口方向", "B. 字体", "C. 题号", "D. 页码"],
                        "answer": "A",
                    },
                ],
                "self_test_phrase": "能说清参数与图像的对应关系。",
            }
        ]

        normalized = normalize_final_review_plan(plan)

        self.assertEqual(
            [blank["answer"] for blank in normalized["days"][0]["blanks"]],
            ["a 的符号", "(h, k)", "$x=-b/(2a)$"],
        )
        self.assertFalse(any(item.get("type") == "fill" for item in normalized["days"][0]["items"]))
        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
        )
        self.assertTrue(review.passed, [issue.description for issue in review.issues])

    def test_quality_gate_does_not_treat_option_word_tihao_as_vague_reference(self):
        plan = valid_single_lesson_plan(subject="数学", topic="二次函数")
        plan["days"] = [
            {
                "day": 1,
                "goal": "复盘二次函数图像与参数。",
                "blanks": [
                    {"text": "二次函数图像开口由______决定。", "answer": "a 的符号"},
                    {"text": "顶点式中顶点坐标是______。", "answer": "(h, k)"},
                    {"text": "对称轴公式是______。", "answer": "$x=-b/(2a)$"},
                ],
                "choices": [
                    {
                        "question": "判断二次函数图像最值前，应先看哪一项？",
                        "options": ["A. 开口方向", "B. 字体大小", "C. 题号颜色", "D. 页码位置"],
                        "answer": "A",
                    },
                    {
                        "question": "顶点式最适合先读出什么信息？",
                        "options": ["A. 顶点坐标", "B. 题号", "C. 字体", "D. 页码"],
                        "answer": "A",
                    },
                ],
                "self_test_phrase": "能说清参数与图像的对应关系。",
            }
        ]

        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
        )

        self.assertTrue(review.passed, [issue.description for issue in review.issues])

    def test_quality_gate_flags_actual_vague_question_reference(self):
        plan = valid_single_lesson_plan(subject="数学", topic="二次函数")
        plan["days"] = [
            {
                "day": 1,
                "goal": "复盘二次函数图像与参数。",
                "blanks": [
                    {"text": "二次函数图像开口由______决定。", "answer": "a 的符号"},
                    {"text": "顶点式中顶点坐标是______。", "answer": "(h, k)"},
                    {"text": "对称轴公式是______。", "answer": "$x=-b/(2a)$"},
                ],
                "choices": [
                    {
                        "question": "原题中这个题的正确入口是什么？",
                        "options": ["A. 先看开口", "B. 先看题号", "C. 先看字体", "D. 先看页码"],
                        "answer": "A",
                    },
                    {
                        "question": "顶点式最适合先读出什么信息？",
                        "options": ["A. 顶点坐标", "B. 字体大小", "C. 页码", "D. 颜色"],
                        "answer": "A",
                    },
                ],
            }
        ]

        review = review_single_lesson_plan(plan, subject="math")

        self.assertTrue(any("模糊指代" in issue.description for issue in review.issues))

    def test_compressed_fallback_blueprint_requires_complete_one_day_density(self):
        blueprint = _fallback_agent_blueprint(
            review_input=ReviewPlanInput(
                summary_text="课堂讲了勾股定理和勾股数应用。",
                subject="数学",
                topic="勾股定理及勾股数应用",
                schedule_mode="compressed",
                review_days=[1],
            ),
            subject="math",
            source=SourceSummary(confirmed_topics=["勾股定理", "勾股数"]),
            task_blueprint=TaskBlueprint(subject="math", required_components=[]),
        )

        instructions = "\n".join(blueprint.writer_instructions)
        criteria = "\n".join(blueprint.success_criteria)
        self.assertIn("只输出 day=1", instructions)
        self.assertIn("至少提供 5 个不重复的可打印题目", instructions)
        self.assertIn("worked_example", instructions)
        self.assertIn("error_log", criteria)

    def test_review_plan_input_accepts_custom_review_days(self):
        review_input = ReviewPlanInput(
            summary_text="课堂总结",
            schedule_mode="custom",
            review_days=[1, 5],
            user_requirements="只做考前两次",
        )

        self.assertEqual(review_input.review_days, [1, 5])
        self.assertEqual(review_input.user_requirements, "只做考前两次")

    def test_quality_policy_skips_llm_reviewer_for_high_confidence_local_pass(self):
        from review_plan_workflow.quality_policy import should_run_llm_quality_review
        from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief

        local_quality = QualityReview(score=96, passed=True, must_revise=False, issues=[], revision_instructions=[])
        source_brief = ReviewPlanSourceBrief(
            source_text_hash="sha256:" + "c" * 64,
            cleaned_text="课堂材料",
            lesson_title_candidates=["一次函数"],
            confidence=0.86,
        )

        self.assertFalse(should_run_llm_quality_review(local_quality=local_quality, source_brief=source_brief))

    def test_quality_policy_runs_llm_reviewer_when_source_confidence_is_low(self):
        from review_plan_workflow.quality_policy import should_run_llm_quality_review
        from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief

        local_quality = QualityReview(score=92, passed=True, must_revise=False, issues=[], revision_instructions=[])
        source_brief = ReviewPlanSourceBrief(confidence=0.5, missing_fields=["topic"])

        self.assertTrue(should_run_llm_quality_review(local_quality=local_quality, source_brief=source_brief))

    def test_quality_policy_caps_structural_revision_attempts_to_one(self):
        from review_plan_workflow.quality_policy import max_revision_attempts_for_quality
        from review_plan_workflow.schemas import QualityIssue, QualityReview, ReviewPlanSourceBrief

        quality = QualityReview(
            score=40,
            passed=False,
            must_revise=True,
            issues=[QualityIssue(severity="high", category="pdf_readiness", description="题量不足")],
            revision_instructions=["补足题目"],
        )
        source_brief = ReviewPlanSourceBrief(confidence=0.82)

        self.assertEqual(max_revision_attempts_for_quality(quality=quality, source_brief=source_brief), 1)

    def test_quality_policy_allows_second_revision_for_question_factual_errors(self):
        from review_plan_workflow.quality_policy import max_revision_attempts_for_quality
        from review_plan_workflow.schemas import ReviewPlanSourceBrief

        quality = QualityReview(
            score=62,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="question_quality",
                    description="第1天选择题答案错误，应为锐角三角形。",
                    suggested_fix="重写该选择题并校验答案。",
                )
            ],
            revision_instructions=["重写选择题并校验答案"],
        )
        source_brief = ReviewPlanSourceBrief(confidence=0.82)

        self.assertEqual(max_revision_attempts_for_quality(quality=quality, source_brief=source_brief), 2)

    def test_quality_policy_softens_workload_after_revision_only_when_no_other_high_issue(self):
        from review_plan_workflow.quality_policy import can_soft_pass_after_revision, soften_quality_after_revision

        workload_quality = QualityReview(
            score=70,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="workload_sanity",
                    description="第1天任务量超过30分钟。",
                    suggested_fix="减少任务或调整时间。",
                )
            ],
            revision_instructions=["减少任务或调整时间"],
        )

        self.assertTrue(can_soft_pass_after_revision(workload_quality))
        softened = soften_quality_after_revision(workload_quality)
        self.assertTrue(softened.passed)
        self.assertFalse(softened.must_revise)
        self.assertEqual(softened.score, 85)
        self.assertEqual(softened.issues[0].severity, "medium")

        mixed_quality = QualityReview(
            score=50,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(severity="high", category="workload_sanity", description="任务太多。"),
                QualityIssue(severity="high", category="question_quality", description="选择题答案错误。"),
            ],
            revision_instructions=["修复问题"],
        )
        self.assertFalse(can_soft_pass_after_revision(mixed_quality))

    def test_question_repair_localizes_cn_choice_issue(self):
        from review_plan_workflow.nodes.question_repair import find_question_repair_targets

        plan = normalize_final_review_plan(writer_style_single_lesson_plan())
        quality = QualityReview(
            score=62,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="question_quality",
                    description="第1天选择题第2题答案错误：应为锐角三角形，不是直角三角形。",
                    suggested_fix="重写第1天选择题第2题，并重新验算答案。",
                )
            ],
            revision_instructions=["重写错题"],
        )

        targets = find_question_repair_targets(plan, quality)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].target_id, "day1_choice2")
        self.assertEqual(targets[0].kind, "choice")
        self.assertEqual(targets[0].question["question"], "解分式方程后为什么要代回原分母检验？")

    def test_question_repair_rejects_unlocalized_structural_issue(self):
        from review_plan_workflow.nodes.question_repair import find_question_repair_targets

        quality = QualityReview(
            score=40,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="schema",
                    description="review plan must include review days",
                    suggested_fix="补齐 days",
                )
            ],
            revision_instructions=["补齐结构"],
        )

        self.assertEqual(find_question_repair_targets(writer_style_single_lesson_plan(), quality), [])

    def test_question_repair_uses_structured_target_path(self):
        from review_plan_workflow.nodes.question_repair import find_question_repair_targets

        plan = normalize_final_review_plan(writer_style_single_lesson_plan())
        quality = QualityReview(
            score=60,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="factuality",
                    description="答案验算错误。",
                    suggested_fix="重写该选择题答案。",
                    target_path="days[0].choices[1]",
                )
            ],
            revision_instructions=["按 target_path 修复"],
        )

        targets = find_question_repair_targets(plan, quality)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].target_id, "day1_choice2")

    def test_question_repair_target_path_uses_day_array_position(self):
        from review_plan_workflow.nodes.question_repair import find_question_repair_targets

        plan = normalize_final_review_plan(writer_style_single_lesson_plan())
        quality = QualityReview(
            score=60,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="factuality",
                    description="第 7 天第二道选择题答案验算错误。",
                    suggested_fix="重写该选择题答案。",
                    target_path="days[2].choices[1]",
                )
            ],
            revision_instructions=["按 target_path 修复"],
        )

        targets = find_question_repair_targets(plan, quality)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].target_id, "day7_choice2")

    def test_source_brief_builder_records_structured_source_before_writer(self):
        from review_plan_workflow.executor import run_workflow_node
        from review_plan_workflow.nodes.intake_normalizer import intake_normalizer_node
        from review_plan_workflow.nodes.source_brief_builder import source_brief_builder_node
        from review_plan_workflow.state import WorkflowContext

        review_input = ReviewPlanInput(
            summary_text=(
                "本节课主题：动点与立体几何综合\n"
                "老师强调：先看固定量，再判断轨迹。\n"
                "例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？"
            ),
            subject="数学",
            grade="六年级",
            user_requirements="压缩成一天，少一点题量",
        )
        context = WorkflowContext(provider="deepseek", model="deepseek-v4-pro")
        normalized = run_workflow_node(intake_normalizer_node, review_input, context)
        brief = run_workflow_node(
            source_brief_builder_node,
            {"input": review_input, "normalized": normalized},
            context,
        )

        self.assertEqual(brief.lesson_title_candidates[0], "动点与立体几何综合")
        self.assertTrue(brief.evidence_map)
        self.assertIn("source_brief", context.node_outputs)
        trace_source_brief = context.node_outputs["source_brief"]
        self.assertEqual(trace_source_brief["schema_version"], "2026-07-01")
        self.assertIn("cleaned_text_length", trace_source_brief)
        self.assertNotIn("cleaned_text", trace_source_brief)
        self.assertNotIn("压缩成一天，少一点题量", str(trace_source_brief))
        executor_source_brief = context.node_outputs["source_brief_builder"]
        self.assertIn("cleaned_text_length", executor_source_brief)
        self.assertNotIn("cleaned_text", executor_source_brief)

    def test_source_brief_builder_warns_on_missing_fields_without_leaking_cleaned_text(self):
        from review_plan_workflow.executor import run_workflow_node
        from review_plan_workflow.nodes.intake_normalizer import intake_normalizer_node
        from review_plan_workflow.nodes.source_brief_builder import source_brief_builder_node
        from review_plan_workflow.state import WorkflowContext

        review_input = ReviewPlanInput(
            summary_text="今天讲了很多内容，学生容易把条件看漏。",
            subject="数学",
            grade="六年级",
        )
        context = WorkflowContext(provider="deepseek", model="deepseek-v4-pro")
        normalized = run_workflow_node(intake_normalizer_node, review_input, context)
        brief = run_workflow_node(
            source_brief_builder_node,
            {"input": review_input, "normalized": normalized},
            context,
        )

        self.assertIn("topic", brief.missing_fields)
        self.assertIn("source_brief_missing_fields", [warning.code for warning in context.warnings])
        self.assertNotIn("cleaned_text", context.node_outputs["source_brief_builder"])

    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_service_passes_source_brief_and_user_requirements_to_planner_and_writer(
        self,
        mock_parent_plan,
        mock_generate_plan,
        mock_llm_review,
    ):
        config_runtime.write_file_config({"deepseek_api_key": "test-key"})
        mock_parent_plan.return_value = (
            {
                "strategy_summary": "按源材料聚焦空间轨迹",
                "student_diagnosis": ["空间轨迹判断不稳"],
                "knowledge_map": [{"name": "空间轨迹", "role": "核心", "evidence": "ev-001"}],
                "day_strategies": [
                    {
                        "day": 1,
                        "objective": "压缩复习",
                        "retrieval_focus": ["轨迹"],
                        "question_design": ["填空"],
                        "review_loop": ["自检"],
                        "risk_controls": ["不虚构"],
                    }
                ],
                "writer_instructions": ["只用源材料证据"],
                "quality_risks": [],
                "success_criteria": ["题目可打印"],
                "assumptions": [],
                "confidence": 0.9,
            },
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 1, "output_tokens": 2},
        )
        mock_generate_plan.return_value = (
            valid_single_lesson_plan(subject="数学", topic="动点与立体几何综合"),
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 3, "output_tokens": 4},
        )
        mock_llm_review.return_value = (
            {"score": 96, "passed": True, "must_revise": False, "issues": [], "revision_instructions": []},
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 5, "output_tokens": 6},
        )

        generate_single_lesson_review_plan(
            summary_text=(
                "本节课主题：动点与立体几何综合\n"
                "老师强调：先看固定量，再判断轨迹。\n"
                "例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？"
            ),
            subject="数学",
            grade="六年级",
            topic="",
            weak_points="空间轨迹",
            lesson_date="2026-07-01",
            generation_options={
                "schedule_mode": "compressed",
                "user_requirements": "压缩成一天，少一点题量，多做诊断",
            },
            provider="deepseek",
            model="deepseek-v4-pro",
        )

        parent_message = mock_parent_plan.call_args.kwargs["user_message"]
        writer_message = mock_generate_plan.call_args.kwargs["user_message"]
        self.assertIn("source_brief", parent_message)
        self.assertIn("压缩成一天，少一点题量，多做诊断", parent_message)
        self.assertIn("结构化课堂材料", writer_message)
        self.assertIn("动点与立体几何综合", writer_message)
        self.assertIn("压缩成一天，少一点题量，多做诊断", writer_message)

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_service_node_outputs_do_not_store_source_text_quotes(self, mock_generate_plan):
        classroom_phrase = "这段课堂材料不要落库：先看固定量，再判断轨迹。"
        mock_generate_plan.return_value = (
            valid_single_lesson_plan(subject="数学", topic="动点与立体几何综合"),
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 3, "output_tokens": 4},
        )
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-01",
            subject="数学",
            grade="六年级",
            topic="动点与立体几何综合",
            summary=classroom_phrase,
            weak_points="空间轨迹",
        )

        generate_single_lesson_review_plan(
            summary_text=classroom_phrase,
            subject="数学",
            grade="六年级",
            topic="动点与立体几何综合",
            weak_points="空间轨迹",
            lesson_date="2026-07-01",
            provider="deepseek",
            model="deepseek-v4-pro",
            lesson_id=lesson_id,
            organization_id=1,
        )

        writer_message = mock_generate_plan.call_args.kwargs["user_message"]
        self.assertIn(classroom_phrase, writer_message)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        node_outputs_blob = json.dumps(run["node_outputs"], ensure_ascii=False)
        self.assertNotIn(classroom_phrase, node_outputs_blob)
        self.assertNotIn("先看固定量，再判断轨迹", node_outputs_blob)
        self.assertNotIn('"cleaned_text":', node_outputs_blob)

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

    def test_validate_final_review_plan_normalizes_nested_tasks_into_printable_fields(self):
        raw_plan = valid_single_lesson_plan(subject="数学", topic="动点与立体几何综合")
        for day in raw_plan["days"]:
            day["blanks"] = []
            day["choices"] = []
            day["items"] = []
            day["tasks"] = {
                "blanks": [
                    {"stem": f"第{day['day']}天：定长线段在立体中的轨迹是______。", "answer": "球面"},
                    {"stem": f"第{day['day']}天：球面被平面截得的图形是______。", "answer": "圆"},
                    {"stem": f"第{day['day']}天：面积最值先找固定底或固定______。", "answer": "高"},
                ],
                "choices": [
                    {
                        "question": f"第{day['day']}天：到定点距离为定长的动点轨迹是？",
                        "options": ["A. 球面", "B. 直线", "C. 射线", "D. 折线"],
                        "answer": "A",
                    },
                    {
                        "question": f"第{day['day']}天：定底三角形面积最值优先看什么？",
                        "options": ["A. 动高", "B. 颜色", "C. 页码", "D. 字体"],
                        "answer": "A",
                    },
                ],
                "active_recall": {
                    "cards": [
                        {"stem": f"第{day['day']}天：为什么线面角最大值要找线段最短？", "answer_hint": "垂高固定时，斜线越短角越大。"}
                    ]
                },
            }
        raw_plan["days"][2]["tasks"] = {
            "blanks_spiral": [
                {"stem": "第7天：定长线段在立体中的轨迹是______。", "answer": "球面"},
                {"stem": "第7天：球面被平面截得的图形是______。", "answer": "圆"},
            ],
            "oral_cards": [
                {"stem": "题干：动点 P 满足 PA·PB=0。", "answer_hint": "以 AB 为直径的圆。"},
                {"stem": "题干：动点 P 到定点距离固定。", "answer_hint": "轨迹是球面。"},
                {"stem": "题干：线面角垂高固定。", "answer_hint": "找线段最短。"},
            ],
        }
        raw_plan["days"][3]["tasks"]["multiple_choice_diagnosis"] = {
            "question": "第14天：下列哪一步最能避免空间直觉误判？",
            "options": ["A. 先画关系图", "B. 直接猜", "C. 只看答案", "D. 跳过证明"],
            "answer": "A",
        }

        plan, errors = validate_final_review_plan(raw_plan)
        review = review_single_lesson_plan(raw_plan, subject="math")

        self.assertIsNotNone(plan)
        self.assertEqual(errors, [])
        self.assertEqual(plan.days[0].blanks[0]["text"], "第1天：定长线段在立体中的轨迹是______。")
        self.assertEqual(plan.days[0].choices[0]["question"], "第1天：到定点距离为定长的动点轨迹是？")
        self.assertEqual(len(plan.days[2].blanks), 2)
        self.assertTrue(any("PA·PB=0" in item["text"] for item in plan.days[2].items))
        self.assertTrue(review.passed, review.model_dump())
        self.assertFalse(any(issue.category in {"pdf_readiness", "task_actionability"} for issue in review.issues))

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

    def test_quality_gate_accepts_nested_plan_wrapper_after_normalization(self):
        inner_plan = valid_single_lesson_plan(subject="数学", topic="动点与立体几何综合")
        days = [dict(day) for day in inner_plan["days"]]
        days[2] = {
            "day": 7,
            "objective": "从会做到会讲：完整口述方法链。",
            "oral_cards": [
                {
                    "stem": "题干：动点 P 满足 PA·PB=0。",
                    "question": "为什么这个条件能推出 P 的轨迹是圆？",
                },
                {
                    "stem": "题干：动点 P 到定点距离固定。",
                    "question": "试说出 P 点的轨迹，并解释最值转化思路。",
                },
                {
                    "stem": "题干：线面角垂高固定。",
                    "question": "为什么求最大值时要找线段最短？",
                },
            ],
            "mini_test": {
                "blanks": [
                    {"stem": "定长线段在立体中的轨迹是______。", "answer": "球面"},
                    {"stem": "球面被平面截得的图形是______。", "answer": "圆"},
                    {"stem": "求面积最值时先找不变量，再求______。", "answer": "高或底"},
                ],
                "choices": [
                    {
                        "question": "关于线面角，以下说法正确的是？",
                        "options": ["A. 越长角越大", "B. 越短角越小", "C. 三余弦定理给出最小角", "D. 最大值等于二面角"],
                        "answer": "C",
                    }
                ],
            },
            "active_recall": {
                "items": ["步骤1：判断______；", "步骤2：找到______；", "步骤3：转化为______。"],
                "answers": ["轨迹模型", "不变量", "几何量最值"],
            },
            "completion_criteria": "能流畅口述方法链，并完成当天自测。",
        }
        full_review_topics = [
            "平面动点轨迹判圆",
            "立体动点定长模型",
            "球面截圆",
            "圆锥侧面轨迹",
            "面积最值转化",
            "体积最值转化",
        ]
        wrapped_plan = {
            "subject": "数学",
            "grade": "六年级",
            "topic": "动点与立体几何综合",
            "lesson_date": "2026-07-01",
            "review_days": [1, 2, 7, 14, 30],
            "plan": {
                "full_review_topics": full_review_topics,
                "quotes": ["动点问题的核心是先判断轨迹，再处理最值。"],
                "days": days,
            },
        }

        review = review_single_lesson_plan(wrapped_plan, subject="math")

        self.assertTrue(review.passed, review.model_dump())
        self.assertFalse(any(issue.category in {"schema", "completeness"} for issue in review.issues))

    def test_quality_gate_uses_required_review_days(self):
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        plan["days"] = [day for day in plan["days"] if day["day"] in {1, 7}]

        review = review_single_lesson_plan(plan, subject="math", required_review_days=[1, 7], schedule_mode="custom")

        self.assertTrue(review.passed, review.model_dump())
        self.assertFalse(any(issue.category == "completeness" for issue in review.issues))

    def test_quality_gate_rejects_extra_default_days_for_custom_schedule(self):
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")

        review = review_single_lesson_plan(plan, subject="math", required_review_days=[1], schedule_mode="compressed")

        self.assertFalse(review.passed)
        self.assertTrue(any(issue.category == "completeness" for issue in review.issues))

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

        class FakeClient:
            def __init__(self):
                self.with_options_kwargs = None
                self.chat = type("Chat", (), {})()
                self.chat.completions = type("Completions", (), {})()
                self.chat.completions.create = create_mock

            def with_options(self, **kwargs):
                self.with_options_kwargs = kwargs
                return self

        fake_client = FakeClient()
        with patch.object(llm_client_module, "get_chat_client", return_value=fake_client):
            payload, usage = llm_client_module.generate_review_plan_json(
                system_prompt="system",
                user_message="user",
                provider="deepseek",
                model="deepseek-v4-pro",
                temperature=0.17,
                stage="unit_test_stage",
                timeout_seconds=42.0,
                max_retries=0,
            )

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(usage["input_tokens"], 11)
        self.assertEqual(usage["output_tokens"], 22)
        self.assertEqual(create_mock.call_args.kwargs["timeout"], 42.0)
        self.assertEqual(create_mock.call_args.kwargs["temperature"], 0.17)
        self.assertEqual(fake_client.with_options_kwargs, {"timeout": 42.0, "max_retries": 0})

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
        self.assertEqual(parent_kwargs["timeout_seconds"], 35.0)
        self.assertEqual(parent_kwargs["max_retries"], 0)
        writer_kwargs = mock_generate_plan.call_args.kwargs
        self.assertEqual(writer_kwargs["provider"], "deepseek")
        self.assertEqual(writer_kwargs["model"], "deepseek-v4-pro")
        self.assertEqual(writer_kwargs["temperature"], 0.36)
        self.assertEqual(writer_kwargs["stage"], "plan_generator")
        self.assertEqual(writer_kwargs["timeout_seconds"], 180.0)
        self.assertEqual(writer_kwargs["max_retries"], 0)
        self.assertIn("父模型教学蓝图", writer_kwargs["user_message"])
        self.assertIn("定义域", writer_kwargs["user_message"])
        reviewer_kwargs = mock_llm_review.call_args.kwargs
        self.assertEqual(reviewer_kwargs["provider"], "openai")
        self.assertEqual(reviewer_kwargs["temperature"], 0.08)
        self.assertEqual(reviewer_kwargs["stage"], "quality_reviewer_llm")
        self.assertEqual(reviewer_kwargs["timeout_seconds"], 90.0)
        self.assertEqual(reviewer_kwargs["max_retries"], 0)
        self.assertIn("trusted_workflow_metadata", reviewer_kwargs["user_message"])
        self.assertIn('"grade": "高一"', reviewer_kwargs["user_message"])
        self.assertIn("不要因为课堂材料里没重复出现这些字段", reviewer_kwargs["user_message"])
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertIn("parent_planner", run["node_outputs"])
        self.assertIn("quality_reviewer_llm", run["node_outputs"])
        self.assertEqual(run["node_outputs"]["plan_generator_model_config"]["temperature"], 0.36)

    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_service_skips_llm_reviewer_for_high_confidence_local_pass(
        self,
        mock_parent_plan,
        mock_generate_plan,
        mock_llm_review,
    ):
        config_runtime.write_file_config({
            "openai_api_key": "test-openai",
            "deepseek_api_key": "test-deepseek",
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-5.4",
        })
        mock_parent_plan.return_value = (
            {
                "strategy_summary": "围绕一次函数表达式和斜率判断复习。",
                "student_diagnosis": ["斜率判断不稳"],
                "knowledge_map": [{"name": "一次函数", "role": "核心", "evidence": "ev-001"}],
                "day_strategies": [
                    {"day": day, "objective": "一次函数复习", "retrieval_focus": ["斜率", "表达式"]}
                    for day in [1, 2, 7, 14, 30]
                ],
                "writer_instructions": ["每天绑定斜率判断。"],
                "quality_risks": [],
                "success_criteria": ["题目可打印"],
                "assumptions": [],
                "confidence": 0.9,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 1, "output_tokens": 2},
        )
        mock_generate_plan.return_value = (
            valid_single_lesson_plan(subject="数学", topic="一次函数"),
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 3, "output_tokens": 4},
        )

        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-01",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂材料",
            weak_points="斜率判断",
        )
        _generated, usage = generate_single_lesson_review_plan(
            summary_text=(
                "本节课主题：一次函数\n"
                "知识点：函数表达式与图像。\n"
                "方法：先代入 -> 再化简 -> 最后检验。\n"
                "老师强调：先看斜率，再判断增减性。\n"
                "例题：已知 y=2x+1，求 x=3 时 y 的值？"
            ),
            subject="数学",
            grade="初二",
            topic="一次函数",
            weak_points="斜率判断",
            lesson_date="2026-07-01",
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        mock_llm_review.assert_not_called()
        self.assertEqual(usage["input_tokens"], 4)
        self.assertEqual(usage["output_tokens"], 6)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["node_outputs"]["quality_reviewer_initial"]["mode"], "skipped")
        self.assertEqual(
            run["node_outputs"]["quality_reviewer_initial"]["reason"],
            "local_quality_passed_with_high_source_confidence",
        )

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
        self.assertEqual(revise_kwargs["provider"], "deepseek")
        self.assertEqual(revise_kwargs["model"], "deepseek-v4-pro")
        self.assertEqual(revise_kwargs["temperature"], 0.1)
        self.assertEqual(revise_kwargs["timeout_seconds"], 120.0)
        self.assertEqual(revise_kwargs["max_retries"], 0)
        self.assertIn("父模型教学蓝图", revise_kwargs["user_message"])
        self.assertIn("定义域遗漏", revise_kwargs["user_message"])
        self.assertEqual(usage["input_tokens"], 75)
        self.assertEqual(usage["output_tokens"], 34)

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_workload_sanity_issue_revises_once_then_soft_passes(
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
            "review_plan_writer_provider": "deepseek",
            "review_plan_writer_model": "deepseek-v4-pro",
        })
        mock_parent_plan.return_value = (
            {
                "strategy_summary": "压缩复习，但保持任务可执行。",
                "student_diagnosis": ["需要集中复习"],
                "knowledge_map": [{"name": "小数运算", "role": "核心", "evidence": "课堂"}],
                "day_strategies": [{"day": 1, "objective": "小数运算集中复习"}],
                "writer_instructions": ["优先减少任务量，不要阻断生成。"],
                "quality_risks": ["任务量可能偏重。"],
                "success_criteria": ["能完成核心题目。"],
                "assumptions": [],
                "confidence": 0.82,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 5, "output_tokens": 2},
        )
        initial_plan = valid_single_lesson_plan(subject="数学", topic="小数运算")
        initial_plan["days"] = initial_plan["days"][:1]
        initial_plan["days"][0]["day"] = 1
        revised_plan = valid_single_lesson_plan(subject="数学", topic="小数运算")
        revised_plan["days"] = revised_plan["days"][:1]
        revised_plan["days"][0]["day"] = 1
        revised_plan["days"][0]["completion_standard"] = "完成核心题后记录一个错因即可。"
        mock_generate_plan.return_value = (
            initial_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 5},
        )
        workload_issue = {
            "severity": "high",
            "category": "workload_sanity",
            "description": "第1天标注30分钟，但实际包含20多项产出，五年级学生无法稳定完成。",
            "suggested_fix": "减少任务量或调整完成标准。",
        }
        mock_llm_review.side_effect = [
            (
                {"score": 70, "passed": False, "must_revise": True, "issues": [workload_issue], "revision_instructions": ["压缩任务量"]},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {"score": 76, "passed": False, "must_revise": True, "issues": [workload_issue], "revision_instructions": ["仍偏重，但不影响内容可用"]},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
        ]
        mock_revise_plan.return_value = (
            revised_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 7, "output_tokens": 4},
        )

        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-02",
            subject="数学",
            grade="五年级",
            topic="小数运算",
            summary="课堂总结文本",
            weak_points="任务量偏重",
        )

        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="五年级",
            topic="小数运算",
            lesson_date="2026-07-02",
            generation_options={"schedule_mode": "compressed", "review_days": [1]},
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        self.assertEqual([day["day"] for day in generated["days"]], [1])
        self.assertEqual(mock_revise_plan.call_count, 1)
        self.assertEqual(mock_llm_review.call_count, 2)
        self.assertEqual(usage["input_tokens"], 28)
        self.assertEqual(usage["output_tokens"], 13)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["quality_review"]["passed"], True)
        self.assertEqual(run["quality_review"]["must_revise"], False)
        self.assertEqual(run["quality_review"]["score"], 85)
        self.assertEqual(run["quality_review"]["issues"][0]["severity"], "medium")
        self.assertTrue(any(warning["code"] == "quality_workload_soft_pass" for warning in run["warnings"]))

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.question_repair.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_question_answer_error_gets_second_targeted_revision(
        self,
        mock_parent_plan,
        mock_generate_plan,
        mock_llm_review,
        mock_question_repair,
        mock_revise_plan,
    ):
        config_runtime.write_file_config({
            "openai_api_key": "test-openai",
            "deepseek_api_key": "test-deepseek",
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-5.4",
            "review_plan_writer_provider": "deepseek",
            "review_plan_writer_model": "deepseek-v4-pro",
        })
        mock_parent_plan.return_value = (
            {
                "strategy_summary": "校验勾股定理逆定理和三角形分类。",
                "student_diagnosis": ["容易把锐角三角形误判为直角三角形"],
                "knowledge_map": [{"name": "勾股逆定理", "role": "判断三角形类型", "evidence": "课堂"}],
                "day_strategies": [{"day": day, "objective": "勾股数判断"} for day in [1, 2, 7, 14, 30]],
                "writer_instructions": ["每道选择题必须验算答案。"],
                "quality_risks": ["选择题答案可能算错。"],
                "success_criteria": ["选择题答案必须与验算一致。"],
                "assumptions": [],
                "confidence": 0.82,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 5, "output_tokens": 2},
        )
        initial_plan = writer_style_single_lesson_plan()
        initial_plan["lesson_info"]["topic"] = "勾股定理及勾股数应用"
        mock_generate_plan.return_value = (
            initial_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 5},
        )
        factual_issue = {
            "severity": "high",
            "category": "question_quality",
            "description": "第1天选择题第2题答案错误：应为锐角三角形，不是直角三角形。",
            "suggested_fix": "重写第1天选择题第2题，并重新验算答案。",
        }
        mock_llm_review.side_effect = [
            (
                {"score": 62, "passed": False, "must_revise": True, "issues": [factual_issue], "revision_instructions": ["重写错题"]},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {"score": 70, "passed": False, "must_revise": True, "issues": [factual_issue], "revision_instructions": ["继续重写错题"]},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {"score": 95, "passed": True, "must_revise": False, "issues": [], "revision_instructions": []},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
        ]
        mock_question_repair.side_effect = [
            (
                {
                    "repairs": [
                        {
                            "target_id": "day1_choice2",
                            "kind": "choice",
                            "question": "三边为 $\\sqrt{3}$、$\\sqrt{4}$、$\\sqrt{5}$ 的三角形是什么三角形？",
                            "options": ["A. 直角三角形", "B. 钝角三角形", "C. 等边三角形", "D. 不存在"],
                            "answer": "A",
                            "analysis": "第一次修复仍错误，审稿会继续拦截。",
                        }
                    ]
                },
                {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 7, "output_tokens": 4},
            ),
            (
                {
                    "repairs": [
                        {
                            "target_id": "day1_choice2",
                            "kind": "choice",
                            "question": "三边为 $\\sqrt{3}$、$\\sqrt{4}$、$\\sqrt{5}$ 的三角形是什么三角形？",
                            "options": ["A. 直角三角形", "B. 锐角三角形", "C. 钝角三角形", "D. 不存在"],
                            "answer": "B",
                            "analysis": "最大边平方为 5，另外两边平方和为 7，5<7，所以是锐角三角形。",
                        }
                    ]
                },
                {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 8, "output_tokens": 4},
            ),
        ]

        generated, usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="九年级",
            topic="勾股定理及勾股数应用",
            weak_points="勾股逆定理分类判断",
            lesson_date="2026-07-02",
            include_usage=True,
        )

        self.assertEqual(generated["days"][0]["choices"][1]["answer"], "B")
        self.assertIn("锐角三角形", generated["days"][0]["choices"][1]["analysis"])
        self.assertEqual(mock_question_repair.call_count, 2)
        mock_revise_plan.assert_not_called()
        self.assertEqual(mock_llm_review.call_count, 3)
        self.assertEqual(mock_question_repair.call_args_list[0].kwargs["stage"], "question_repair")
        self.assertEqual(mock_question_repair.call_args_list[0].kwargs["provider"], "deepseek")
        self.assertEqual(mock_question_repair.call_args_list[0].kwargs["model"], "deepseek-v4-pro")
        self.assertEqual(mock_question_repair.call_args_list[0].kwargs["timeout_seconds"], 45.0)
        self.assertIn("day1_choice2", mock_question_repair.call_args_list[0].kwargs["user_message"])
        self.assertNotIn("当前计划 JSON", mock_question_repair.call_args_list[0].kwargs["user_message"])
        self.assertEqual(usage["provider"], "openai")

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
    def test_service_passes_generation_options_through_workflow(self, mock_generate_plan):
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        plan["days"] = [day for day in plan["days"] if day["day"] in {1, 7}]
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

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="初二",
            topic="一次函数",
            weak_points="斜率判断",
            lesson_date="2026-06-01",
            lesson_id=lesson_id,
            organization_id=1,
            generation_options={
                "schedule_mode": "custom",
                "review_days": [1, 7],
                "user_requirements": "只做两次，题量轻一点",
            },
            include_usage=True,
        )

        self.assertEqual([day["day"] for day in generated["days"]], [1, 7])
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["node_outputs"]["scope_planner"]["review_days"], [1, 7])
        options = run["node_outputs"]["prompt_bundle_builder"]["variables"]["generation_options"]
        self.assertEqual(options["schedule_mode"], "custom")
        self.assertEqual(options["review_days"], [1, 7])
        self.assertEqual(options["user_requirements"], "只做两次，题量轻一点")
        self.assertIn("复习日必须且只能覆盖 [1, 7]", mock_generate_plan.call_args.kwargs["user_message"])

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
    def test_output_normalization_trusts_lesson_metadata_and_removes_unsupported_quotes(self, mock_generate_plan):
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        plan["lesson_info"]["subject"] = ""
        plan["lesson_info"]["grade"] = ""
        plan["lesson_info"]["assumptions"] = ["年级'九年级'为学生用户输入，课堂材料中不可核验。", "主题来自课堂材料。"]
        plan["quotes"] = ["老师说一定要这样做。"]
        plan["days"][0]["quotes"] = ["老师原话：先看题号。"]
        mock_generate_plan.return_value = (
            plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="九年级",
            topic="一次函数",
            lesson_date="2026-07-02",
            provider="deepseek",
            model="deepseek-v4-pro",
            include_usage=True,
        )

        self.assertEqual(generated["lesson_info"]["subject"], "数学")
        self.assertEqual(generated["lesson_info"]["grade"], "九年级")
        self.assertEqual(generated["lesson_info"]["date"], "2026-07-02")
        self.assertEqual(generated["lesson_info"]["assumptions"], ["主题来自课堂材料。"])
        self.assertEqual(generated["quotes"], [])
        self.assertEqual(generated["days"][0].get("quotes"), [])

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
    def test_plan_generator_retries_transient_connection_error_once(self, mock_generate_plan):
        valid_plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        mock_generate_plan.side_effect = [
            RuntimeError("Connection error."),
            (valid_plan, {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 5, "output_tokens": 6}),
        ]
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

        self.assertEqual(generated["lesson_info"]["topic"], "一次函数")
        self.assertEqual(validate_final_review_plan(generated)[1], [])
        self.assertEqual(usage["input_tokens"], 5)
        self.assertEqual(mock_generate_plan.call_count, 2)
        self.assertEqual(mock_generate_plan.call_args_list[0].kwargs["stage"], "plan_generator")
        self.assertEqual(mock_generate_plan.call_args_list[1].kwargs["stage"], "plan_generator_retry")
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertTrue(any(warning["code"] == "plan_generator_transient_retry" for warning in run["warnings"]))

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
        self.assertFalse(any(warning["code"].startswith("plan_generator_schema") for warning in run["warnings"]))
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
        self.assertEqual(generated["lesson_info"]["grade"], "九年级")
        self.assertEqual([day["day"] for day in generated["days"]], [1, 2, 7, 14, 30])
        self.assertEqual(
            generated["full_review_topics"],
            ["二次函数最值", "将军饮马最短路径", "上减下/右减左", "设参数表达坐标", "轴对称转化", "顶点公式求最值"],
        )
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertFalse(any(warning["code"].startswith("plan_generator_schema") for warning in run["warnings"]))
        self.assertTrue(run["quality_review"]["passed"])

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_plan_generator_normalizes_nested_plan_wrapper_without_schema_warning(self, mock_generate_plan):
        inner_plan = valid_single_lesson_plan(subject="数学", topic="动点与立体几何综合")
        full_review_topics = [
            "平面动点轨迹判圆",
            "立体动点定长模型",
            "球面截圆",
            "圆锥侧面轨迹",
            "面积最值转化",
            "体积最值转化",
        ]
        mock_generate_plan.return_value = (
            {
                "subject": "数学",
                "lesson_date": "2026-07-01",
                "lesson_info": {"subject": "math", "topic": "", "grade": "", "date": "2026-07-01", "key_categories": []},
                "full_review_topics": [],
                "quotes": [],
                "days": [],
                "review_days": [1, 2, 7, 14, 30],
                "plan": {
                    "full_review_topics": full_review_topics,
                    "quotes": ["动点问题的核心是先判断轨迹，再处理最值。"],
                    "days": inner_plan["days"],
                },
            },
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )

        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-01",
            subject="数学",
            grade="六年级",
            topic="动点与立体几何综合",
            summary="课堂总结文本",
            weak_points="",
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="六年级",
            topic="动点与立体几何综合",
            lesson_date="2026-07-01",
            provider="deepseek",
            model="deepseek-v4-pro",
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        self.assertEqual(generated["lesson_info"]["topic"], "动点与立体几何综合")
        self.assertEqual([day["day"] for day in generated["days"]], [1, 2, 7, 14, 30])
        self.assertEqual(validate_final_review_plan(generated)[1], [])
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertFalse(any(warning["code"].startswith("plan_generator_schema") for warning in run["warnings"]))
        self.assertTrue(run["quality_review"]["passed"])

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_plan_generator_normalizes_common_result_wrapper_without_schema_repair(self, mock_generate_plan):
        inner_plan = valid_single_lesson_plan(subject="数学", topic="圆与动点综合")
        mock_generate_plan.return_value = (
            {
                "result": {
                    "plan": inner_plan,
                },
            },
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="课堂总结文本",
            subject="数学",
            grade="六年级",
            topic="圆与动点综合",
            lesson_date="2026-07-01",
            provider="deepseek",
            model="deepseek-v4-pro",
            include_usage=True,
        )

        self.assertEqual(generated["lesson_info"]["topic"], "圆与动点综合")
        self.assertEqual([day["day"] for day in generated["days"]], [1, 2, 7, 14, 30])
        self.assertEqual(validate_final_review_plan(generated)[1], [])
        self.assertEqual(mock_generate_plan.call_count, 1)
        user_message = mock_generate_plan.call_args.kwargs["user_message"]
        self.assertIn("顶层必须直接包含 lesson_info, full_review_topics, quotes, days", user_message)
        self.assertIn("禁止输出 plan, reviewPlan, result, data, output, content, response 等包裹字段", user_message)

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
    def test_service_returns_best_plan_with_warning_after_one_failed_revision(self, mock_generate_plan, mock_revise_plan):
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
        self.assertEqual(usage["input_tokens"], 11)
        self.assertEqual(usage["output_tokens"], 22)
        self.assertEqual(mock_revise_plan.call_count, 1)
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
