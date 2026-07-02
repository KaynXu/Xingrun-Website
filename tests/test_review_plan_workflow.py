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
    NormalizedBrief,
    QualityIssue,
    QualityReview,
    ReviewPlanInput,
    ReviewPlanSourceBrief,
    ScopePlan,
    SourceKnowledgePoint,
    SourceSummary,
    TaskBlueprint,
    normalize_final_review_plan,
    validate_final_review_plan,
)
from review_plan_workflow.service import (
    _fallback_agent_blueprint,
    _normalize_output_plan,
    _repair_source_coverage_gaps,
    _should_skip_parent_planner,
    generate_single_lesson_review_plan,
)
from review_plan_workflow.source_brief import build_deterministic_source_brief, source_brief_trace_payload
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

    def test_compressed_single_day_normalization_adds_lightweight_spiral_review(self):
        plan = valid_single_lesson_plan(subject="数学", topic="勾股数与特殊角推导")
        plan["days"] = [plan["days"][0]]
        plan["days"][0]["day"] = 1
        plan["days"][0].pop("spiral_review", None)
        review_input = ReviewPlanInput(
            summary_text="勾股数、特殊角度αβ与和角推导完整课堂逐字稿",
            subject="数学",
            grade="高一",
            topic="勾股数与特殊角推导",
            schedule_mode="compressed",
            review_days=[1],
            user_requirements="生成当天的复习计划，题目控制在10个题",
        )

        normalized = _normalize_output_plan(plan, review_input)

        self.assertIn("spiral_review", normalized["days"][0])
        self.assertIn("交叉回收", normalized["days"][0]["spiral_review"][0])
        self.assertIn("隔题复现", normalized["days"][0]["spiral_review"][1])

    def test_normalizes_task_blocks_for_compressed_day_quality_gate(self):
        plan = {
            "lesson_info": {"subject": "数学", "grade": "八年级", "date": "2026-07-02", "topic": "勾股数与特殊角复习"},
            "full_review_topics": ["整数勾股数", "根式勾股数", "特殊角 α β", "α+β=45°"],
            "quotes": ["难题高频勾股比要求脱口而出。"],
            "days": [
                {
                    "day": 1,
                    "label": "当天课后复习",
                    "goal": "用填空、选择和口述卡复盘勾股数组与特殊角推导。",
                    "completion_standard": "填空和选择订正完成，并能口述 α+β=45° 的关键比例。",
                    "blanks": [],
                    "choices": [],
                    "task_blocks": [
                        {
                            "type": "blanks",
                            "items": [
                                {"question": "最基础的整数勾股数组是什么？", "answer": "3:4:5"},
                                {"question": "1:1:√2 对应的直角三角形两个锐角都是______。", "answer": "45°"},
                                {"question": "1:√3:2 中短直角边对应的角是______。", "answer": "30°"},
                                {"question": "α 对应的勾股比是______。", "answer": "1:2:√5"},
                                {"question": "β 对应的勾股比是______。", "answer": "1:3:√10"},
                            ],
                        },
                        {
                            "type": "choices",
                            "items": [
                                {
                                    "question": "若三边满足 a²+b²=c²，可以判断三角形是什么三角形？",
                                    "options": ["A. 直角三角形", "B. 锐角三角形", "C. 钝角三角形", "D. 等边三角形"],
                                    "answer": "A",
                                },
                                {
                                    "question": "2α 与 2β 的关系是？",
                                    "options": ["A. 互余", "B. 相等", "C. 互补", "D. 无法判断"],
                                    "answer": "A",
                                },
                            ],
                        },
                        {
                            "type": "active_recall",
                            "items": [
                                {"question": "口述 α+β=45° 的构造思路。"},
                                {"question": "说明为什么 2α、2β 对应 3:4:5。"},
                            ],
                        },
                    ],
                }
            ],
        }

        normalized = normalize_final_review_plan(plan)
        day = normalized["days"][0]
        self.assertEqual(len(day["blanks"]), 5)
        self.assertEqual(len(day["choices"]), 2)
        self.assertEqual(day["blanks"][0]["answer"], "3:4:5")

        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
        )

        self.assertTrue(review.passed, [issue.description for issue in review.issues])
        self.assertFalse(any(issue.category == "pdf_readiness" for issue in review.issues))

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

    def test_time_allocator_uses_readable_label_for_compressed_one_day_plan(self):
        from review_plan_workflow.nodes.time_allocator import time_allocator_node
        from review_plan_workflow.executor import run_workflow_node
        from review_plan_workflow.state import WorkflowContext

        allocation = run_workflow_node(
            time_allocator_node,
            {
                "normalized": NormalizedBrief(subject="math", confidence=0.8),
                "scope": ScopePlan(review_days=[1], review_loop=["定义回看", "错因复盘"]),
            },
            WorkflowContext(),
        )

        self.assertEqual(allocation.review_schedule[0]["label"], "当天课后复习")

    def test_review_plan_input_accepts_custom_review_days(self):
        review_input = ReviewPlanInput(
            summary_text="课堂总结",
            schedule_mode="custom",
            review_days=[1, 5],
            user_requirements="只做考前两次",
            constraints={"requested_question_count": 10},
        )

        self.assertEqual(review_input.review_days, [1, 5])
        self.assertEqual(review_input.user_requirements, "只做考前两次")
        self.assertEqual(review_input.constraints["requested_question_count"], 10)

    def test_quality_issue_accepts_nullable_locator_fields_from_llm_reviewer(self):
        issue = QualityIssue(
            severity="high",
            category="question_quality",
            description="第1天选择题第2题答案错误。",
            question_type=None,
            target_path=None,
            suggested_fix=None,
        )

        self.assertEqual(issue.question_type, "")
        self.assertEqual(issue.target_path, "")
        self.assertEqual(issue.suggested_fix, "")

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

    def test_quality_policy_skips_llm_reviewer_for_soft_source_gap(self):
        from review_plan_workflow.quality_policy import should_run_llm_quality_review
        from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief

        local_quality = QualityReview(score=100, passed=True, must_revise=False, issues=[], revision_instructions=[])
        source_brief = ReviewPlanSourceBrief(confidence=0.65, missing_fields=["example_stems"])

        self.assertFalse(should_run_llm_quality_review(local_quality=local_quality, source_brief=source_brief))

    def test_quality_policy_uses_local_revision_without_llm_reviewer(self):
        from review_plan_workflow.quality_policy import should_run_llm_quality_review
        from review_plan_workflow.schemas import QualityIssue, QualityReview, ReviewPlanSourceBrief

        local_quality = QualityReview(
            score=75,
            passed=False,
            must_revise=True,
            issues=[QualityIssue(severity="high", category="source_coverage", description="缺少课堂链路")],
            revision_instructions=["补齐课堂链路"],
        )
        source_brief = ReviewPlanSourceBrief(confidence=0.65, missing_fields=["example_stems"])

        self.assertFalse(should_run_llm_quality_review(local_quality=local_quality, source_brief=source_brief))

    def test_quality_policy_skips_llm_reviewer_when_validator_blocks_delivery(self):
        from review_plan_workflow.quality_policy import should_run_llm_quality_review
        from review_plan_workflow.schemas import QualityReview, ReviewPlanSourceBrief

        local_quality = QualityReview(score=50, passed=False, must_revise=True, issues=[], revision_instructions=[])
        source_brief = ReviewPlanSourceBrief(confidence=0.2, missing_fields=["topic"])

        self.assertFalse(
            should_run_llm_quality_review(
                local_quality=local_quality,
                source_brief=source_brief,
                validator_passed=False,
            )
        )

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

    def test_quality_policy_limits_question_factual_errors_to_one_targeted_repair(self):
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

        self.assertEqual(max_revision_attempts_for_quality(quality=quality, source_brief=source_brief), 1)

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

    def test_quality_policy_softens_low_source_evidence_issue_but_not_wrong_answer(self):
        from review_plan_workflow.quality_policy import can_soft_pass_after_revision, soften_quality_after_revision

        evidence_quality = QualityReview(
            score=72,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="factuality",
                    description=(
                        "计划把具体知识点作为复习主体，但 source_brief 明确缺失 topic 和 "
                        "knowledge_points，lesson_title_candidates_count 为 0，属于证据边界问题。"
                    ),
                    suggested_fix="改成待确认复习范围。",
                )
            ],
            revision_instructions=["将推测内容写入 assumptions"],
        )

        self.assertTrue(can_soft_pass_after_revision(evidence_quality))
        softened = soften_quality_after_revision(evidence_quality)
        self.assertTrue(softened.passed)
        self.assertFalse(softened.must_revise)
        self.assertEqual(softened.issues[0].severity, "medium")

        wrong_answer_quality = QualityReview(
            score=62,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="factuality",
                    description="第1天选择题第2题答案错误：应为锐角三角形，不是直角三角形。",
                    suggested_fix="重写该题并校验答案。",
                )
            ],
            revision_instructions=["修复错题"],
        )

        self.assertFalse(can_soft_pass_after_revision(wrong_answer_quality))

        schema_quality = QualityReview(
            score=40,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="schema",
                    description="review_days 缺失，PDF 无法渲染。",
                    suggested_fix="补齐 days。",
                )
            ],
            revision_instructions=["补齐结构"],
        )

        self.assertFalse(can_soft_pass_after_revision(schema_quality))

    def test_quality_policy_softens_spiral_review_only_issue_after_revision(self):
        from review_plan_workflow.quality_policy import (
            can_soft_pass_after_revision,
            soften_quality_after_revision,
            soft_pass_warning_for_quality,
        )

        quality = QualityReview(
            score=82,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="review_loop",
                    description="计划缺少明确的 spiral_review 组件，需要补充交叉回收或隔题复现。",
                    suggested_fix="补一个轻量 spiral_review。",
                )
            ],
            revision_instructions=["补充 spiral_review"],
        )

        self.assertTrue(can_soft_pass_after_revision(quality))
        softened = soften_quality_after_revision(quality)
        self.assertTrue(softened.passed)
        self.assertFalse(softened.must_revise)
        self.assertEqual(softened.issues[0].severity, "medium")
        self.assertEqual(soft_pass_warning_for_quality(quality)[0], "quality_review_loop_soft_pass")

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

    def test_question_repair_localizes_active_recall_and_blank_paths(self):
        from review_plan_workflow.nodes.question_repair import find_question_repair_targets

        plan = normalize_final_review_plan(writer_style_single_lesson_plan())
        day = plan["days"][0]
        day["active_recall"] = {
            "items": [
                {"instruction": "默写 3:4:5、5:12:13。", "expected": "两组基础勾股数。"},
                {"instruction": "说明 1:2:√5 中 α 的定义。", "expected": "1 对 α。"},
                {"instruction": "错误推导：$\\frac{\\sqrt{2}+2}{4\\sqrt{2}}=1$，所以 α+β=45°。"},
            ]
        }
        while len(day["blanks"]) < 6:
            day["blanks"].append({"text": f"占位填空{len(day['blanks']) + 1}______。", "answer": "占位"})
        quality = QualityReview(
            score=72,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="question_quality",
                    description="days[0].active_recall[2] 的 α+β 推导出现数学错误。",
                    suggested_fix="改用正切和角公式验证。",
                    target_path="days[0].active_recall[2]",
                    day=1,
                ),
                QualityIssue(
                    severity="high",
                    category="pdf_safety",
                    description="days[0].blanks[5] 的公式中出现中文问号。",
                    suggested_fix="把中文问号改成变量 x。",
                    target_path="days[0].blanks[5]",
                    day=1,
                    question_index=6,
                    question_type="blank",
                ),
            ],
            revision_instructions=["局部修复主动回忆和填空题"],
        )

        targets = find_question_repair_targets(plan, quality)

        self.assertEqual([target.target_id for target in targets], ["day1_recall3", "day1_blank6"])
        self.assertEqual(targets[0].kind, "active_recall")
        self.assertEqual(targets[0].active_recall_key, "items")

    def test_question_repair_applies_active_recall_repair(self):
        from review_plan_workflow.nodes.question_repair import _apply_repairs, find_question_repair_targets

        plan = normalize_final_review_plan(writer_style_single_lesson_plan())
        day = plan["days"][0]
        day["active_recall"] = [
            {"instruction": "默写基础勾股数。"},
            {"instruction": "说明 α、β 的定义。"},
            {"instruction": "错误推导：$\\frac{\\sqrt{2}+2}{4\\sqrt{2}}=1$。"},
        ]
        quality = QualityReview(
            score=72,
            passed=False,
            must_revise=True,
            issues=[
                QualityIssue(
                    severity="high",
                    category="question_quality",
                    description="days[0].active_recall[2] 的 α+β 推导出现数学错误。",
                    suggested_fix="改用正切和角公式验证。",
                    target_path="days[0].active_recall[2]",
                    day=1,
                )
            ],
            revision_instructions=["局部修复主动回忆"],
        )
        targets = find_question_repair_targets(plan, quality)

        repaired = _apply_repairs(
            plan,
            targets,
            {
                "repairs": [
                    {
                        "target_id": "day1_recall3",
                        "kind": "active_recall",
                        "instruction": (
                            "已知 $\\tan\\alpha=\\frac{1}{2}$、$\\tan\\beta=\\frac{1}{3}$，"
                            "用正切和角公式证明 $\\alpha+\\beta=45^\\circ$。"
                        ),
                        "expected": (
                            "$\\tan(\\alpha+\\beta)=\\frac{1/2+1/3}{1-1/6}=1$，"
                            "所以 $\\alpha+\\beta=45^\\circ$。"
                        ),
                    }
                ]
            },
        )

        repaired_card = repaired["days"][0]["active_recall"][2]
        self.assertIn("\\tan\\alpha", repaired_card["instruction"])
        self.assertIn("=1", repaired_card["expected"])
        self.assertNotIn("\\frac{\\sqrt{2}+2}{4\\sqrt{2}}=1", json.dumps(repaired_card, ensure_ascii=False))

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
                "constraints": {"force_parent_planner": True},
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

    def test_quality_gate_enforces_requested_question_count_constraint(self):
        plan = valid_single_lesson_plan(subject="数学", topic="勾股数与特殊角推导")
        plan["full_review_topics"] = ["勾股定理", "整数勾股数", "根式勾股数", "特殊角", "和角推导"]
        plan["days"] = [plan["days"][0]]
        plan["days"][0]["day"] = 1
        plan["days"][0]["blanks"] = [
            {"text": f"第{i}题：勾股定理等式为______。", "answer": "$a^2+b^2=c^2$"}
            for i in range(1, 6)
        ]
        plan["days"][0]["choices"] = [
            {
                "question": f"第{i}题：下列哪组是勾股数？",
                "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                "answer": "A",
            }
            for i in range(1, 3)
        ]

        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
            constraints={"requested_question_count": 10},
        )

        self.assertFalse(review.passed)
        self.assertTrue(any("老师要求题目控制在 10 道" in issue.description for issue in review.issues))

    def test_quality_gate_rejects_thin_one_day_plan_missing_source_key_chains(self):
        transcript = (
            "勾股数、特殊角度αβ与和角推导完整课堂逐字稿\n"
            "第一部分：整数勾股数（奇数型、偶数型）、根式勾股数讲解\n"
            "说话人1：逆向判断时，三角形三边满足 a²+b²=c² 才能判定直角三角形。\n"
            "第二部分：α、β定义，互余角勾股比规律\n"
            "第三部分：和角推导——α+β=45°\n"
            "说话人1：β 三角形斜边和上面线段等长，先算一份长度，再按份数还原两条直角边。\n"
            "第四部分：二倍角构造与3:4:5勾股数推导\n"
            "说话人1：作垂直平分线构造二倍角，得到 2α 对应 4:3:5，2β 对应 3:4:5。\n"
            "说话人1：课后继续用相同辅助线方法推导 4β 的勾股比。"
        )
        source_brief = build_deterministic_source_brief(
            raw_text=transcript,
            subject="数学",
            topic="勾股数与特殊角推导",
            user_requirements="当天课后复习，题目控制在10道题。",
        )
        plan = valid_single_lesson_plan(subject="数学", topic="勾股数与特殊角推导")
        plan["full_review_topics"] = ["勾股定理", "整数勾股数", "根式勾股数", "特殊角", "αβ 定义"]
        plan["days"] = [plan["days"][0]]
        plan["days"][0]["day"] = 1
        plan["days"][0]["blanks"] = [
            {"text": f"第{i}题：勾股定理等式为______。", "answer": "$a^2+b^2=c^2$"}
            for i in range(1, 7)
        ]
        plan["days"][0]["choices"] = [
            {
                "question": f"第{i}题：下列哪组是勾股数？",
                "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                "answer": "A",
            }
            for i in range(1, 5)
        ]
        plan["days"][0]["active_recall"] = {"instructions": "口述勾股定理公式。"}

        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
            constraints={"requested_question_count": 10},
            source_brief=source_brief,
        )

        self.assertFalse(review.passed)
        descriptions = "\n".join(issue.description for issue in review.issues)
        self.assertIn("关键知识链路", descriptions)
        self.assertIn("勾股逆向", descriptions)
        self.assertIn("source_coverage", {issue.category for issue in review.issues})
        self.assertTrue(any(issue.category == "source_coverage" and issue.severity == "high" for issue in review.issues))

    def test_quality_gate_treats_single_missing_source_key_chain_as_revision_blocker(self):
        transcript = (
            "勾股数、特殊角度αβ与和角推导完整课堂逐字稿\n"
            "说话人1：必须背熟 3:4:5、5:12:13。\n"
            "说话人1：先算一份长度，再按份数还原两条直角边。\n"
            "说话人1：通过构造推出 α+β=45°，再推出 2α、2β 互余。\n"
            "说话人1：作垂直平分线构造二倍角，得到 2α 对应 4:3:5。\n"
            "说话人1：一元二次方程配方法推导过程要重新演算。"
        )
        source_brief = build_deterministic_source_brief(
            raw_text=transcript,
            subject="数学",
            topic="勾股数与特殊角推导",
            user_requirements="当天课后复习，题目控制在10道题。",
        )
        plan = valid_single_lesson_plan(subject="数学", topic="勾股数与特殊角推导")
        plan["full_review_topics"] = ["整数勾股数", "份数计算", "α+β 和角推导", "二倍角关系", "垂直平分线构造"]
        plan["days"] = [plan["days"][0]]
        plan["days"][0]["day"] = 1
        plan["days"][0]["blanks"] = [
            {"text": "3:4:5 中斜边是______。", "answer": "5"},
            {"text": "先算______长度，再还原两条直角边。", "answer": "一份"},
            {"text": "课堂推导得到 α+β=______。", "answer": "45°"},
            {"text": "2α 和 2β 的关系是______。", "answer": "互余"},
            {"text": "二倍角构造要作______。", "answer": "垂直平分线"},
            {"text": "4β 继续沿用______方法追问。", "answer": "二倍角构造"},
        ]
        plan["days"][0]["choices"] = [
            {
                "question": f"第{i}题：下列哪组是勾股数？",
                "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                "answer": "A",
            }
            for i in range(1, 5)
        ]
        plan["days"][0]["active_recall"] = {
            "items": [
                {"text": "口述份数计算、α+β、2α、2β、4β 的课堂链路。", "answer": "按课堂顺序复述。"}
            ]
        }

        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
            constraints={"requested_question_count": 10},
            source_brief=source_brief,
        )

        self.assertFalse(review.passed)
        self.assertTrue(review.must_revise)
        self.assertTrue(
            any(
                issue.category == "source_coverage"
                and issue.severity == "high"
                and "配方法推导" in issue.description
                for issue in review.issues
            )
        )

    def test_quality_gate_allows_completion_standard_to_say_correct_answer(self):
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        plan["days"][0]["completion_standard"] = "选择题选出正确答案，并能说明错误选项的原因。"
        plan["days"][0]["self_test_phrase"] = "选择题选出正确答案。"

        review = review_single_lesson_plan(plan, subject="math")

        self.assertTrue(review.passed, review.model_dump())
        self.assertFalse(any(issue.category == "style" for issue in review.issues))

    def test_complex_compressed_math_keeps_parent_planner(self):
        transcript = (
            "勾股数、特殊角度αβ与和角推导完整课堂逐字稿\n"
            "说话人1：逆向：三角形三边满足a²+b²=c²才能判定直角三角形。\n"
            "说话人1：先算一份长度，再按份数还原两条直角边。\n"
            "说话人1：通过构造推出 α+β=45°，再推出 2α、2β 互余。\n"
            "说话人1：一元二次方程配方法推导过程要重新演算。"
        )
        source_brief = build_deterministic_source_brief(
            raw_text=transcript,
            subject="数学",
            topic="勾股数、特殊角度αβ与和角推导",
            user_requirements="生成当天的复习计划，题目控制在10个题",
        )
        review_input = ReviewPlanInput(
            summary_text=transcript,
            subject="数学",
            schedule_mode="compressed",
            review_days=[1],
            user_requirements="生成当天的复习计划，题目控制在10个题",
            constraints={"requested_question_count": 10},
        )

        self.assertFalse(_should_skip_parent_planner(review_input=review_input, source_brief=source_brief))

    def test_source_brief_trace_includes_coverage_requirements_without_raw_text(self):
        transcript = (
            "勾股数、特殊角度αβ与和角推导完整课堂逐字稿\n"
            "说话人1：逆向：三角形三边满足a²+b²=c²才能判定直角三角形。\n"
            "说话人1：先算一份长度，再按份数还原两条直角边。\n"
            "说话人1：通过构造推出 α+β=45°，再推出 2α、2β 互余。\n"
            "说话人1：一元二次方程配方法推导过程要重新演算。"
        )
        source_brief = build_deterministic_source_brief(
            raw_text=transcript,
            subject="数学",
            topic="勾股数、特殊角度αβ与和角推导",
        )

        trace = source_brief_trace_payload(source_brief, subject_key="math")

        requirements = trace["coverage_requirements"]
        labels = [item["label"] for item in requirements]
        self.assertIn("勾股逆向：三角形三边满足 a²+b²=c²", labels)
        self.assertIn("配方法推导", labels)
        self.assertNotIn("cleaned_text", trace)

    def test_source_coverage_repair_fills_missing_key_chains_before_failure(self):
        transcript = (
            "勾股数、特殊角度αβ与和角推导完整课堂逐字稿\n"
            "说话人1：逆向：三角形三边满足a²+b²=c²才能判定直角三角形。\n"
            "说话人1：先算一份长度，再按份数还原两条直角边。\n"
            "说话人1：通过构造推出 α+β=45°，再推出 2α、2β 互余。\n"
            "说话人1：一元二次方程配方法推导过程要重新演算。"
        )
        source_brief = build_deterministic_source_brief(
            raw_text=transcript,
            subject="数学",
            topic="勾股数、特殊角度αβ与和角推导",
            user_requirements="生成当天的复习计划，题目控制在10个题",
        )
        review_input = ReviewPlanInput(
            summary_text=transcript,
            subject="数学",
            schedule_mode="compressed",
            review_days=[1],
            user_requirements="生成当天的复习计划，题目控制在10个题",
            constraints={"requested_question_count": 10},
        )
        plan = valid_single_lesson_plan(subject="数学", topic="勾股数、特殊角度αβ与和角推导")
        plan["days"] = [plan["days"][0]]
        plan["days"][0]["day"] = 1
        plan["full_review_topics"] = ["整数勾股数", "特殊角定义", "基础勾股比", "互余角关系", "二倍角关系"]
        plan["days"][0]["blanks"] = [
            {"text": f"第{i}题：3:4:5 中斜边是______。", "answer": "5"}
            for i in range(1, 7)
        ]
        plan["days"][0]["choices"] = [
            {
                "question": f"第{i}题：下列哪组是勾股数？",
                "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                "answer": "A",
            }
            for i in range(1, 5)
        ]
        plan["days"][0]["active_recall"] = {"items": [{"text": "口述整数勾股数。", "answer": "按课堂顺序。"}]}

        initial_review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
            constraints={"requested_question_count": 10},
            source_brief=source_brief,
        )
        self.assertTrue(any(issue.category == "source_coverage" for issue in initial_review.issues))

        repaired, labels = _repair_source_coverage_gaps(
            plan,
            review_input=review_input,
            source_brief=source_brief,
            subject="math",
        )
        repaired_review = review_single_lesson_plan(
            repaired,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
            constraints={"requested_question_count": 10},
            source_brief=source_brief,
        )

        self.assertIn("勾股逆向：三角形三边满足 a²+b²=c²", labels)
        self.assertIn("配方法推导", labels)
        self.assertFalse(any(issue.category == "source_coverage" for issue in repaired_review.issues))
        active_recall_text = json.dumps(repaired["days"][0]["active_recall"], ensure_ascii=False)
        self.assertIn("配方法推导", active_recall_text)
        self.assertIn("勾股逆向", active_recall_text)

    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    def test_service_deterministically_repairs_source_coverage_before_returning(self, mock_generate_plan):
        transcript = (
            "勾股数、特殊角度αβ与和角推导完整课堂逐字稿\n"
            "说话人1：逆向：三角形三边满足a²+b²=c²才能判定直角三角形。\n"
            "说话人1：先算一份长度，再按份数还原两条直角边。\n"
            "说话人1：通过构造推出 α+β=45°，再推出 2α、2β 互余。\n"
            "说话人1：一元二次方程配方法推导过程要重新演算。"
        )
        plan = valid_single_lesson_plan(subject="数学", topic="勾股数、特殊角度αβ与和角推导")
        plan["days"] = [plan["days"][0]]
        plan["days"][0]["day"] = 1
        plan["full_review_topics"] = ["整数勾股数", "特殊角定义", "基础勾股比", "互余角关系", "二倍角关系"]
        plan["days"][0]["blanks"] = [
            {"text": f"第{i}题：3:4:5 中斜边是______。", "answer": "5"}
            for i in range(1, 7)
        ]
        plan["days"][0]["choices"] = [
            {
                "question": f"第{i}题：下列哪组是勾股数？",
                "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                "answer": "A",
            }
            for i in range(1, 5)
        ]
        plan["days"][0]["active_recall"] = {"items": [{"text": "口述整数勾股数。", "answer": "按课堂顺序。"}]}
        mock_generate_plan.return_value = (
            plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 20},
        )
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-03",
            subject="数学",
            grade="高一",
            topic="勾股数、特殊角度αβ与和角推导",
            summary=transcript,
            weak_points="当天课后复习",
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text=transcript,
            subject="数学",
            grade="高一",
            topic="勾股数、特殊角度αβ与和角推导",
            weak_points="当天课后复习",
            lesson_date="2026-07-03",
            lesson_id=lesson_id,
            organization_id=1,
            generation_options={
                "schedule_mode": "compressed",
                "review_days": [1],
                "user_requirements": "生成当天的复习计划，题目控制在10个题",
                "constraints": {"requested_question_count": 10},
            },
            include_usage=True,
        )

        output_text = json.dumps(generated, ensure_ascii=False)
        self.assertIn("勾股逆向：三角形三边满足 a²+b²=c²", output_text)
        self.assertIn("配方法推导", output_text)
        self.assertIn("口述课堂关键链路", output_text)
        review = review_single_lesson_plan(
            generated,
            subject="math",
            required_review_days=[1],
            schedule_mode="compressed",
            constraints={"requested_question_count": 10},
            source_brief=build_deterministic_source_brief(
                raw_text=transcript,
                subject="数学",
                topic="勾股数、特殊角度αβ与和角推导",
                user_requirements="生成当天的复习计划，题目控制在10个题",
            ),
        )
        self.assertFalse(any(issue.category == "source_coverage" for issue in review.issues))
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertIn("source_coverage_repair_initial", run["node_outputs"])

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
        self.assertIn("弱素材兜底契约", writer_kwargs["user_message"])
        reviewer_kwargs = mock_llm_review.call_args.kwargs
        self.assertEqual(reviewer_kwargs["provider"], "openai")
        self.assertEqual(reviewer_kwargs["temperature"], 0.08)
        self.assertEqual(reviewer_kwargs["stage"], "quality_reviewer_llm")
        self.assertEqual(reviewer_kwargs["timeout_seconds"], 90.0)
        self.assertEqual(reviewer_kwargs["max_retries"], 0)
        self.assertIn("trusted_workflow_metadata", reviewer_kwargs["user_message"])
        self.assertIn('"grade": "高一"', reviewer_kwargs["user_message"])
        self.assertIn("不要因为课堂材料里没重复出现这些字段", reviewer_kwargs["user_message"])
        self.assertIn("弱素材降级", reviewer_kwargs["user_message"])
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
        mock_parent_plan.assert_not_called()
        self.assertEqual(usage["input_tokens"], 3)
        self.assertEqual(usage["output_tokens"], 4)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(
            run["node_outputs"]["parent_planner_skipped"]["reason"],
            "deterministic_source_fast_path",
        )
        self.assertTrue(run["node_outputs"]["review_plan_validator_initial"]["passed"])
        self.assertTrue(run["node_outputs"]["review_plan_evaluator"]["passed"])
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
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_low_source_evidence_issue_revises_once_then_soft_passes(
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
                "strategy_summary": "课堂材料证据弱，生成数学通用基础复习。",
                "student_diagnosis": ["课堂主题需老师确认"],
                "knowledge_map": [
                    {"name": "数学基础复习（待确认）", "role": "保持可练习", "evidence": "low_source_fallback"}
                ],
                "day_strategies": [{"day": 1, "objective": "完成通用基础复习"}],
                "writer_instructions": ["标注待确认，不要伪装成课堂事实。"],
                "quality_risks": ["source_brief 缺 topic/knowledge_points。"],
                "success_criteria": ["题目可打印且答案正确。"],
                "assumptions": ["课堂主题需老师确认"],
                "confidence": 0.55,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 5, "output_tokens": 2},
        )
        initial_plan = valid_single_lesson_plan(subject="数学", topic="数学基础复习（待确认）")
        initial_plan["days"] = initial_plan["days"][:1]
        initial_plan["days"][0]["day"] = 1
        initial_plan["assumptions"] = ["课堂主题需老师确认"]
        revised_plan = valid_single_lesson_plan(subject="数学", topic="数学基础复习（待确认）")
        revised_plan["days"] = revised_plan["days"][:1]
        revised_plan["days"][0]["day"] = 1
        revised_plan["assumptions"] = ["课堂主题需老师确认"]
        mock_generate_plan.return_value = (
            initial_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 5},
        )
        evidence_issue = {
            "severity": "high",
            "category": "factuality",
            "description": (
                "计划使用待确认知识点，但 source_brief 明确缺失 topic 和 knowledge_points，"
                "lesson_title_candidates_count 为 0，属于低证据边界提醒。"
            ),
            "suggested_fix": "保留可用题目，但把知识点标为待确认范围。",
        }
        mock_llm_review.side_effect = [
            (
                {"score": 72, "passed": False, "must_revise": True, "issues": [evidence_issue], "revision_instructions": ["标注待确认范围"]},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {"score": 78, "passed": False, "must_revise": True, "issues": [evidence_issue], "revision_instructions": ["仍是低证据提醒"]},
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
            topic="",
            summary="课堂材料很短。",
            weak_points="",
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="课堂材料很短。",
            subject="数学",
            grade="五年级",
            topic="",
            lesson_date="2026-07-02",
            generation_options={"schedule_mode": "compressed", "review_days": [1]},
            lesson_id=lesson_id,
            organization_id=1,
            include_usage=True,
        )

        self.assertEqual([day["day"] for day in generated["days"]], [1])
        self.assertEqual(mock_revise_plan.call_count, 1)
        self.assertEqual(mock_llm_review.call_count, 2)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertEqual(run["quality_review"]["passed"], True)
        self.assertEqual(run["quality_review"]["must_revise"], False)
        self.assertEqual(run["quality_review"]["score"], 85)
        self.assertEqual(run["quality_review"]["issues"][0]["severity"], "medium")
        self.assertTrue(any(warning["code"] == "quality_evidence_soft_pass" for warning in run["warnings"]))

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.question_repair.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_question_answer_error_gets_single_targeted_repair(
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
                {"score": 95, "passed": True, "must_revise": False, "issues": [], "revision_instructions": []},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
        ]
        mock_question_repair.return_value = (
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
            )
        )

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
        self.assertEqual(mock_question_repair.call_count, 1)
        mock_revise_plan.assert_not_called()
        self.assertEqual(mock_llm_review.call_count, 2)
        self.assertEqual(mock_question_repair.call_args_list[0].kwargs["stage"], "question_repair")
        self.assertEqual(mock_question_repair.call_args_list[0].kwargs["provider"], "deepseek")
        self.assertEqual(mock_question_repair.call_args_list[0].kwargs["model"], "deepseek-v4-pro")
        self.assertEqual(mock_question_repair.call_args_list[0].kwargs["timeout_seconds"], 45.0)
        self.assertIn("day1_choice2", mock_question_repair.call_args_list[0].kwargs["user_message"])
        self.assertNotIn("当前计划 JSON", mock_question_repair.call_args_list[0].kwargs["user_message"])
        self.assertEqual(usage["provider"], "openai")

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.question_repair.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_question_issue_after_full_revision_gets_targeted_repair_before_failure(
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
                "strategy_summary": "先修正无证据话术，再校验题目答案。",
                "student_diagnosis": ["容易把三角形分类算错"],
                "knowledge_map": [{"name": "勾股逆定理", "role": "分类判断", "evidence": "课堂"}],
                "day_strategies": [{"day": 1, "objective": "当天课后复习"}],
                "writer_instructions": ["不要写无证据老师原话。"],
                "quality_risks": ["选择题答案可能算错。"],
                "success_criteria": ["题目答案必须验算一致。"],
                "assumptions": [],
                "confidence": 0.82,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 5, "output_tokens": 2},
        )
        initial_plan = writer_style_single_lesson_plan()
        initial_plan["lesson_info"]["topic"] = "勾股定理及勾股数应用"
        initial_plan["days"] = [initial_plan["days"][0]]
        initial_plan["days"][0]["day"] = 1
        initial_plan["days"][0]["active_recall"] = {"instructions": "请默写老师在课堂上强调的两组勾股比。"}
        revised_plan = normalize_final_review_plan(initial_plan)
        revised_plan["days"][0]["active_recall"] = {"instructions": "请默写本课需要掌握的两组勾股比。"}
        mock_generate_plan.return_value = (
            initial_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 5},
        )
        mock_revise_plan.return_value = (
            revised_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 9, "output_tokens": 4},
        )
        teacher_claim_issue = {
            "severity": "high",
            "category": "factuality",
            "description": "生成结果包含没有课堂证据的老师原话。",
            "suggested_fix": "删除“老师在课堂上强调”等无证据表述。",
        }
        question_issue = {
            "severity": "high",
            "category": "question_quality",
            "description": "第1天选择题第2题答案错误：应为锐角三角形，不是直角三角形。",
            "suggested_fix": "重写该题并重新验算答案。",
            "target_path": "days[0].choices[1]",
        }
        mock_llm_review.side_effect = [
            (
                {
                    "score": 70,
                    "passed": False,
                    "must_revise": True,
                    "issues": [teacher_claim_issue, question_issue],
                    "revision_instructions": ["删除无证据老师话术并修正错题"],
                },
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {
                    "score": 78,
                    "passed": False,
                    "must_revise": True,
                    "issues": [question_issue],
                    "revision_instructions": ["修正第1天选择题第2题"],
                },
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {"score": 95, "passed": True, "must_revise": False, "issues": [], "revision_instructions": []},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
        ]
        mock_question_repair.return_value = (
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
            )
        )
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-02",
            subject="数学",
            grade="高一",
            topic="勾股定理及勾股数应用",
            summary="勾股定理、根式勾股数和三角形分类。",
            weak_points="三角形分类判断",
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="勾股定理、根式勾股数和三角形分类。",
            subject="数学",
            grade="高一",
            topic="勾股定理及勾股数应用",
            lesson_date="2026-07-02",
            lesson_id=lesson_id,
            organization_id=1,
            generation_options={"schedule_mode": "compressed", "review_days": [1]},
            include_usage=True,
        )

        self.assertEqual(generated["days"][0]["choices"][1]["answer"], "B")
        self.assertEqual(mock_revise_plan.call_count, 1)
        self.assertEqual(mock_question_repair.call_count, 1)
        self.assertEqual(mock_llm_review.call_count, 3)
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["quality_review"]["passed"], True)
        self.assertIn("quality_reviewer_after_question_repair_2", run["node_outputs"])
        self.assertEqual(run["node_outputs"]["question_repair_attempts"][0]["target_ids"], ["day1_choice2"])

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.question_repair.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_failed_question_repair_reports_latest_issue_even_when_score_drops(
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
                "strategy_summary": "先修正无证据话术，再校验题目答案。",
                "student_diagnosis": ["容易把三角形分类算错"],
                "knowledge_map": [{"name": "勾股逆定理", "role": "分类判断", "evidence": "课堂"}],
                "day_strategies": [{"day": 1, "objective": "当天课后复习"}],
                "writer_instructions": ["不要写无证据老师原话。"],
                "quality_risks": ["选择题答案可能算错。"],
                "success_criteria": ["失败原因必须来自最新审稿结果。"],
                "assumptions": [],
                "confidence": 0.82,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 5, "output_tokens": 2},
        )
        initial_plan = writer_style_single_lesson_plan()
        initial_plan["lesson_info"]["topic"] = "勾股定理及勾股数应用"
        initial_plan["days"] = [initial_plan["days"][0]]
        initial_plan["days"][0]["day"] = 1
        initial_plan["days"][0]["active_recall"] = {"instructions": "请默写老师在课堂上强调的两组勾股比。"}
        revised_plan = normalize_final_review_plan(initial_plan)
        revised_plan["days"][0]["active_recall"] = {"instructions": "请默写本课需要掌握的两组勾股比。"}
        mock_generate_plan.return_value = (
            initial_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 5},
        )
        mock_revise_plan.return_value = (
            revised_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 9, "output_tokens": 4},
        )
        teacher_claim_issue = {
            "severity": "high",
            "category": "factuality",
            "description": "生成结果包含没有课堂证据的老师原话。",
            "suggested_fix": "删除“老师在课堂上强调”等无证据表述。",
        }
        question_issue = {
            "severity": "high",
            "category": "question_quality",
            "description": "第1天选择题第2题答案错误：应为锐角三角形，不是直角三角形。",
            "suggested_fix": "重写该题并重新验算答案。",
            "target_path": "days[0].choices[1]",
        }
        latest_issue = {
            "severity": "high",
            "category": "pdf_readiness",
            "description": "第1天填空题第1题公式无法渲染。",
            "suggested_fix": "修复第1天填空题第1题公式。",
        }
        mock_llm_review.side_effect = [
            (
                {
                    "score": 70,
                    "passed": False,
                    "must_revise": True,
                    "issues": [teacher_claim_issue, question_issue],
                    "revision_instructions": ["删除无证据老师话术并修正错题"],
                },
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {
                    "score": 78,
                    "passed": False,
                    "must_revise": True,
                    "issues": [question_issue],
                    "revision_instructions": ["修正第1天选择题第2题"],
                },
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {
                    "score": 60,
                    "passed": False,
                    "must_revise": True,
                    "issues": [latest_issue],
                    "revision_instructions": ["修复第1天填空题第1题公式"],
                },
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
        ]
        mock_question_repair.return_value = (
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
            )
        )
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-02",
            subject="数学",
            grade="高一",
            topic="勾股定理及勾股数应用",
            summary="勾股定理、根式勾股数和三角形分类。",
            weak_points="三角形分类判断",
        )

        generate_single_lesson_review_plan(
            summary_text="勾股定理、根式勾股数和三角形分类。",
            subject="数学",
            grade="高一",
            topic="勾股定理及勾股数应用",
            lesson_date="2026-07-02",
            lesson_id=lesson_id,
            organization_id=1,
            generation_options={"schedule_mode": "compressed", "review_days": [1]},
        )

        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        quality_blob = json.dumps(run["quality_review"], ensure_ascii=False)
        self.assertIn("公式无法渲染", quality_blob)
        self.assertNotIn("选择题第2题答案错误", quality_blob)

    @patch("review_plan_workflow.nodes.revision.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.llm_quality_reviewer.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json")
    @patch("review_plan_workflow.nodes.parent_planner.generate_review_plan_json")
    def test_failed_revision_reports_latest_quality_issue_not_stale_initial_topic_issue(
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
                "strategy_summary": "基于勾股数课堂文本生成当天复习。",
                "student_diagnosis": [],
                "knowledge_map": [{"name": "勾股数与特殊角", "role": "课堂主题", "evidence": "source title"}],
                "day_strategies": [{"day": 1, "objective": "当天课后复习"}],
                "writer_instructions": ["topic 必须来自 source_brief 标题。"],
                "quality_risks": ["α+β 推导题可能不自洽。"],
                "success_criteria": ["题目必须能独立作答。"],
                "assumptions": [],
                "confidence": 0.82,
            },
            {"provider": "openai", "model": "gpt-5.4", "input_tokens": 5, "output_tokens": 2},
        )
        initial_plan = writer_style_single_lesson_plan()
        initial_plan["lesson_info"]["topic"] = ""
        initial_plan["days"] = [initial_plan["days"][0]]
        initial_plan["days"][0]["day"] = 1
        revised_plan = normalize_final_review_plan(initial_plan)
        revised_plan["lesson_info"]["topic"] = "勾股数、特殊角度αβ与和角推导"
        revised_plan["weak_points_summary"] = "按实际填写"
        revised_plan["days"][0]["active_recall"] = {
            "instructions": "用错误拼接方程回忆 α+β=45° 推导。",
            "items": [
                {
                    "text": "$2^2+(1+x)^2=(\\sqrt{5})^2+(\\sqrt{10})^2$ 化简得到的方程是______。",
                    "answer": "7x^2-4x-20=0",
                }
            ],
        }
        revised_plan["days"][0]["blanks"][0]["text"] = "已知 f(x)=begincases 2x, x>0 endcases，则定义域为______。"
        mock_generate_plan.return_value = (
            initial_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 10, "output_tokens": 5},
        )
        mock_revise_plan.return_value = (
            revised_plan,
            {"provider": "deepseek", "model": "deepseek-v4-pro", "input_tokens": 9, "output_tokens": 4},
        )
        stale_topic_issue = {
            "severity": "high",
            "category": "pdf_readiness",
            "description": "lesson_info.topic 为空或退回通用“课后”，PDF 会生成空壳标题。",
            "suggested_fix": "把用户主题或 lesson_topic 映射为 lesson_info.topic。",
        }
        latest_math_issue = {
            "severity": "high",
            "category": "question_quality",
            "description": "active_recall 中的 α+β=45° 推导题不可做且数学关系错误。",
            "suggested_fix": "删除错误拼接方程，改成可验证的同类推导。",
            "target_path": "days[0].active_recall",
            "day": 1,
            "question_index": 11,
            "question_type": "blank",
        }
        mock_llm_review.side_effect = [
            (
                {"score": 74, "passed": False, "must_revise": True, "issues": [stale_topic_issue], "revision_instructions": ["补 topic"]},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
            (
                {"score": 72, "passed": False, "must_revise": True, "issues": [latest_math_issue], "revision_instructions": ["修 active_recall"]},
                {"provider": "openai", "model": "gpt-5.4", "input_tokens": 3, "output_tokens": 1},
            ),
        ]
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-07-02",
            subject="数学",
            grade="高一",
            topic="",
            summary="勾股数、特殊角度αβ与和角推导完整课堂逐字稿",
            weak_points="",
        )

        generated, _usage = generate_single_lesson_review_plan(
            summary_text="勾股数、特殊角度αβ与和角推导完整课堂逐字稿",
            subject="数学",
            grade="高一",
            topic="",
            lesson_date="2026-07-02",
            lesson_id=lesson_id,
            organization_id=1,
            generation_options={"schedule_mode": "compressed", "review_days": [1]},
            include_usage=True,
        )

        self.assertEqual(generated["lesson_info"]["topic"], "勾股数、特殊角度αβ与和角推导")
        run = lesson_manager.get_latest_review_plan_run_for_lesson(lesson_id)
        quality_blob = json.dumps(run["quality_review"], ensure_ascii=False)
        self.assertIn("公式", quality_blob)
        self.assertNotIn("topic 为空", quality_blob)

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
        runtime = run["node_outputs"]["workflow_runtime"]
        self.assertEqual(runtime["path"], "fast_path")
        self.assertEqual(runtime["model_call_count"], 1)
        self.assertEqual(runtime["writer_model_call_count"], 1)
        self.assertEqual(runtime["llm_reviewer_model_call_count"], 0)
        self.assertIn("plan_generator", runtime["latency_by_stage"])
        self.assertEqual(runtime["delivery_contract"]["generation_mode"], "standard")
        self.assertGreater(runtime["delivery_contract"]["visible_question_count"], 0)
        self.assertEqual(
            runtime["delivery_contract"]["visible_question_count"],
            runtime["delivery_contract"]["answer_key_count"],
        )

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
        plan["days"][0]["active_recall"] = {
            "instructions": "请默写老师在课堂上强调的两组必须脱口而出的勾股比。",
            "items": [{"text": "老师提醒：先平方再比较最长边。"}],
        }
        plan["days"][0]["steps"] = [{"description": "课堂原话：列式前先确认哪条边最大。"}]
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
        generated_blob = json.dumps(generated, ensure_ascii=False)
        self.assertNotIn("老师在课堂上强调", generated_blob)
        self.assertNotIn("老师提醒", generated_blob)
        self.assertNotIn("课堂原话", generated_blob)
        self.assertIn("本课需要掌握的两组必须脱口而出的勾股比", generated_blob)

    def test_output_normalization_uses_source_title_when_model_leaves_topic_empty(self):
        plan = valid_single_lesson_plan(subject="数学", topic="")
        plan["lesson_info"]["topic"] = ""
        plan["lesson_info"]["key_categories"] = []
        review_input = ReviewPlanInput(
            summary_text="勾股数、特殊角度αβ与和角推导完整课堂逐字稿\n今天学习勾股定理。",
            subject="数学",
            grade="高一",
            lesson_date="2026-07-02",
        )
        source_brief = ReviewPlanSourceBrief(
            lesson_title_candidates=["勾股数、特殊角度αβ与和角推导"],
            knowledge_points=[
                SourceKnowledgePoint(name="整数勾股数（奇数型、偶数型）", evidence_ids=["ev-002"], confidence=0.68),
                SourceKnowledgePoint(name="α+β=45°推导", evidence_ids=["ev-020"], confidence=0.68),
            ],
        )

        generated = _normalize_output_plan(plan, review_input, source_brief)

        self.assertEqual(generated["lesson_info"]["topic"], "勾股数、特殊角度αβ与和角推导")
        self.assertEqual(
            generated["lesson_info"]["key_categories"],
            ["整数勾股数（奇数型、偶数型）", "α+β=45°推导"],
        )

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

        serialized = app_module._serialize_lesson_for_response(
            lesson_manager.get_lesson(lesson_id),
            include_runtime=True,
        )

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
