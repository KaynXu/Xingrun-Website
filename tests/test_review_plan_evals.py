import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from review_plan_workflow.evals.runner import (
    CHINA_COURSE_MARKERS,
    FIXTURE_ROOT,
    INTERNATIONAL_COURSE_TERMS,
    evaluate_plan_against_fixture,
    evaluate_fixture_assertions,
    iter_fixture_paths,
    load_fixture,
    run_workflow_eval,
    run_workflow_for_fixture,
    validate_all_fixtures,
    validate_fixture_definition,
    workflow_kwargs_from_fixture,
)
from tests.test_review_plan_plan_v1 import valid_plan_v1
from tests.review_plan_test_utils import (
    dynamic_geometry_source_brief_plan,
    text_only_low_density_review_plan,
    valid_single_lesson_plan,
)


def _run_fixture_assertions(plan: dict, fixture: dict) -> None:
    results = evaluate_fixture_assertions(plan, fixture)
    failures = [result for result in results if not result["passed"]]
    if failures:
        rendered = "; ".join(f"{result['name']} failed: {result.get('error', '')}" for result in failures)
        raise AssertionError(rendered)


def _only_assertion(fixture: dict, name: str) -> dict:
    assertions = [assertion for assertion in fixture.get("assertions") or [] if assertion.get("name") == name]
    assert assertions, f"missing fixture assertion: {name}"
    return {
        "assertions": assertions
    }


def _pythagorean_one_day_10q_plan() -> dict:
    plan = valid_plan_v1()
    plan["document_title"] = "勾股数与特殊角"
    plan["audience"]["subject"] = "数学"
    plan["audience"]["grade"] = "高一"
    plan["lesson_summary"] = "复习整数勾股数、根式比例、份数计算、αβ 和角推导、二倍角构造与配方法推导。"
    plan["knowledge_map"] = [
        {"id": "k1", "title": "整数勾股数", "summary": "熟记 3:4:5、5:12:13、7:24:25、9:40:41。"},
        {"id": "k2", "title": "根式勾股数", "summary": "掌握 1:1:√2、1:√3:2、1:2:√5、1:3:√10。"},
        {"id": "k3", "title": "α、β 定义", "summary": "α 和 β 都是短边 1 所对的锐角。"},
        {"id": "k4", "title": "份数计算", "summary": "用斜边比例求一份长度，再还原两条直角边。"},
        {"id": "k5", "title": "α+β=45°", "summary": "能复述构造和比例推导。"},
        {"id": "k6", "title": "二倍角构造", "summary": "2α 对应 4:3:5，2β 对应 3:4:5，并继续追问 4β。"},
        {"id": "k7", "title": "配方法推导", "summary": "能复述一元二次方程配方过程的关键步骤。"},
    ]
    plan["math_blocks"] = [
        {"id": "pythagorean", "latex": "a^2+b^2=c^2", "display": True},
        {"id": "alpha_beta_sum", "latex": "\\alpha+\\beta=45^\\circ", "display": True},
        {"id": "double_angle", "latex": "2\\alpha+2\\beta=90^\\circ", "display": True},
    ]
    plan["teacher_checkpoints"] = [
        {"id": "t1", "text": "基础比例必须脱口而出。"},
        {"id": "t2", "text": "份数计算、二倍角构造和配方法推导必须能口述。"},
    ]
    plan["source_coverage"] = [
        {"source_segment_id": "seg-1", "covered_by": ["k1", "k2", "k3", "k4", "k5", "k6", "k7"]}
    ]
    fill_questions = [
        ("勾股定理中，两条直角边 a、b 和斜边 c 满足______。", "$a^2+b^2=c^2$"),
        ("3、4、5 这组三边中，斜边是______。", "5"),
        ("1:1:√2 对应的直角三角形两个锐角都是______。", "45°"),
        ("β 三角形斜边已知时，先用斜边比例求______长度。", "一份"),
        ("α 表示 1:2:√5 中短边 1 所对的______。", "锐角"),
    ]
    choice_questions = [
        (
            "下列哪一组是整数勾股数？",
            ["A. 3:4:5", "B. 2:3:4", "C. 1:1:3", "D. 4:4:9"],
            "A",
        ),
        (
            "β 对应的是哪组比例中短边 1 所对的角？",
            ["A. 1:3:√10", "B. 1:1:√2", "C. 3:4:5", "D. 5:12:13"],
            "A",
        ),
        (
            "课堂推导得到 α+β 的结果是？",
            ["A. 45°", "B. 60°", "C. 90°", "D. 30°"],
            "A",
        ),
        (
            "继续推导 4β 时，首先要沿用哪种课堂方法？",
            ["A. 斜边的垂直平分线", "B. 任意中线", "C. 角平分线", "D. 平行线"],
            "A",
        ),
    ]
    plan["practice_tasks"] = [
        {
            "id": f"b{index}",
            "day": 1,
            "task_type": "blank",
            "question": question,
            "answer": answer,
            "knowledge_ids": ["k1"],
        }
        for index, (question, answer) in enumerate(fill_questions, start=1)
    ]
    plan["practice_tasks"].extend(
        {
            "id": f"c{index}",
            "day": 1,
            "task_type": "choice",
            "question": question,
            "options": options,
            "answer": answer,
            "knowledge_ids": ["k1"],
        }
        for index, (question, options, answer) in enumerate(choice_questions, start=1)
    )
    plan["self_check_questions"] = [
        {
            "id": "s1",
            "day": 1,
            "question": "口述一遍：先算份数，再推出 α+β=45°，并说明 2α、2β、4β 与配方法推导为什么要继续追问。",
            "answer": "用份数还原边长；α+β=45°；2α 和 2β 互余，4β 继续用二倍角方法追问；配方法用于还原课堂推导步骤。",
        }
    ]
    return plan


class ReviewPlanEvalRunnerTestCase(unittest.TestCase):
    def test_all_eval_fixtures_are_valid(self):
        report = validate_all_fixtures()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["fixture_count"], len(iter_fixture_paths()))

    def test_math_and_physics_fixtures_default_to_china_school_context(self):
        for fixture_path in iter_fixture_paths():
            fixture = load_fixture(fixture_path)
            input_payload = fixture.get("input", {})
            subject = input_payload.get("subject")
            if subject not in {"math", "physics"}:
                continue

            errors = validate_fixture_definition(fixture, fixture_path=str(fixture_path.relative_to(FIXTURE_ROOT)))
            self.assertFalse(errors)
            course_system = input_payload.get("courseSystem", "")
            self.assertTrue(any(marker in course_system for marker in CHINA_COURSE_MARKERS), fixture_path)
            input_text = str(input_payload)
            self.assertFalse(any(term in input_text for term in INTERNATIONAL_COURSE_TERMS), fixture_path)

    def test_eval_runner_passes_valid_math_plan_against_fixture(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertTrue(result["passed"], result)
        self.assertTrue(result["schema_valid"])
        self.assertTrue(result["quality"]["passed"])
        self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_eval_runner_fails_schema_invalid_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)

        result = evaluate_plan_against_fixture({"lesson_info": {"topic": "一次函数"}, "days": []}, fixture)

        self.assertFalse(result["passed"])
        self.assertFalse(result["schema_valid"])
        self.assertTrue(result["schema_errors"])

    def test_eval_runner_fails_forbidden_international_terms_in_math_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)
        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        plan["weak_points_summary"] += " A-Level"

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertFalse(result["passed"])
        default_check = next(check for check in result["checks"] if check["name"] == "no_international_course_default")
        self.assertFalse(default_check["passed"])
        self.assertEqual(default_check["forbidden_found"], ["A-Level"])

    def test_task8_dynamic_geometry_fixture_preserves_source_brief_context(self):
        fixture_path = FIXTURE_ROOT / "math" / "dynamic-geometry-source-brief.json"
        fixture = load_fixture(fixture_path)

        errors = validate_fixture_definition(fixture, fixture_path=str(fixture_path.relative_to(FIXTURE_ROOT)))
        kwargs = workflow_kwargs_from_fixture(fixture)

        self.assertFalse(errors)
        self.assertEqual(kwargs["topic"], "动点与立体几何综合")
        self.assertIn("老师强调", kwargs["summary_text"])
        self.assertIn("动点 P", kwargs["summary_text"])
        self.assertIn("空间轨迹判断", kwargs["weak_points"])
        self.assertEqual(kwargs["generation_options"]["review_days"], [1, 2, 7, 14, 30])
        self.assertIn("真实数学判断", kwargs["generation_options"]["user_requirements"])
        self.assertEqual(fixture["input"]["generation_options"]["review_days"], [1, 2, 7, 14, 30])
        self.assertIn("真实数学判断", fixture["input"]["generation_options"]["user_requirements"])

    def test_task8_dynamic_geometry_assertions_pass_realistic_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "dynamic-geometry-source-brief.json"
        fixture = load_fixture(fixture_path)
        plan = dynamic_geometry_source_brief_plan()

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertTrue(result["passed"], result)
        self.assertTrue(all(assertion["passed"] for assertion in result["assertions"]))
        _run_fixture_assertions(plan, fixture)

    def test_task8_dynamic_geometry_assertions_reject_choice_regressions(self):
        fixture_path = FIXTURE_ROOT / "math" / "dynamic-geometry-source-brief.json"
        fixture = load_fixture(fixture_path)
        cases = {
            "choices_have_complete_options": lambda plan: plan["days"][0]["choices"][0].update(
                {"options": ["A. 球面"], "answer": "A"}
            ),
            "no_generic_checklist_choices": lambda plan: plan["days"][0]["choices"][0].update(
                {
                    "question": "今天应选择哪一组执行清单？",
                    "options": ["A. 先看固定量", "B. 检查边界", "C. 完成复盘", "D. 执行清单"],
                    "answer": "A",
                }
            ),
        }

        for assertion_name, mutate in cases.items():
            with self.subTest(assertion_name=assertion_name):
                plan = dynamic_geometry_source_brief_plan()
                mutate(plan)
                with self.assertRaisesRegex(AssertionError, assertion_name):
                    _run_fixture_assertions(plan, _only_assertion(fixture, assertion_name))

    def test_task8_dynamic_geometry_workflow_eval_rejects_checklist_choices(self):
        fixture_path = FIXTURE_ROOT / "math" / "dynamic-geometry-source-brief.json"
        fixture = load_fixture(fixture_path)

        def fake_generator(**kwargs):
            self.assertEqual(kwargs["generation_options"]["review_days"], [1, 2, 7, 14, 30])
            self.assertIn("真实数学判断", kwargs["generation_options"]["user_requirements"])
            plan = dynamic_geometry_source_brief_plan()
            plan["days"][0]["choices"][0].update(
                {
                    "question": "今天应选择哪一组执行清单？",
                    "options": ["A. 先看固定量", "B. 检查边界", "C. 完成复盘", "D. 执行清单"],
                    "answer": "A",
                }
            )
            return plan, {}

        result = run_workflow_for_fixture(fixture, fixture_path=str(fixture_path), generator=fake_generator)

        self.assertFalse(result["passed"], result)
        failed = [item for item in result["evaluation"]["assertions"] if not item["passed"]]
        self.assertEqual(failed[0]["name"], "no_generic_checklist_choices")

    def test_task8_text_only_low_density_assertions_pass_dense_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "text-only-low-density-review-plan.json"
        fixture = load_fixture(fixture_path)
        plan = text_only_low_density_review_plan()

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertTrue(result["passed"], result)
        self.assertTrue(all(assertion["passed"] for assertion in result["assertions"]))
        _run_fixture_assertions(plan, fixture)

    def test_task8_text_only_low_density_assertions_reject_known_failures(self):
        fixture_path = FIXTURE_ROOT / "math" / "text-only-low-density-review-plan.json"
        fixture = load_fixture(fixture_path)
        cases = {
            "topic_not_empty": lambda plan: plan["lesson_info"].update({"topic": ""}),
            "full_review_topics_minimum": lambda plan: plan.update({"full_review_topics": ["等式判断"]}),
            "minimum_printable_items_per_day": lambda plan: plan["days"][0].update(
                {"items": [], "blanks": plan["days"][0]["blanks"][:1], "choices": []}
            ),
            "no_duplicate_printable_tasks": lambda plan: plan["days"][0]["blanks"].append(
                copy.deepcopy(plan["days"][0]["blanks"][0])
            ),
        }

        for assertion_name, mutate in cases.items():
            with self.subTest(assertion_name=assertion_name):
                plan = text_only_low_density_review_plan()
                mutate(plan)
                with self.assertRaisesRegex(AssertionError, assertion_name):
                    _run_fixture_assertions(plan, _only_assertion(fixture, assertion_name))

    def test_task8_text_only_workflow_eval_rejects_duplicate_printable_tasks(self):
        fixture_path = FIXTURE_ROOT / "math" / "text-only-low-density-review-plan.json"
        fixture = load_fixture(fixture_path)

        def fake_generator(**kwargs):
            self.assertEqual(kwargs["generation_options"]["review_days"], [1, 2, 7, 14, 30])
            self.assertIn("执行清单不能全做选择题", kwargs["generation_options"]["user_requirements"])
            plan = text_only_low_density_review_plan()
            plan["days"][0]["blanks"].append(copy.deepcopy(plan["days"][0]["blanks"][0]))
            return plan, {}

        result = run_workflow_for_fixture(fixture, fixture_path=str(fixture_path), generator=fake_generator)

        self.assertFalse(result["passed"], result)
        failed = [item for item in result["evaluation"]["assertions"] if not item["passed"]]
        self.assertEqual(failed[0]["name"], "no_duplicate_printable_tasks")

    def test_task52_pythagorean_one_day_fixture_checks_renderer_and_source_pack(self):
        fixture_path = FIXTURE_ROOT / "math" / "pythagorean-alpha-beta-one-day-10q.json"
        fixture = load_fixture(fixture_path)
        plan = _pythagorean_one_day_10q_plan()

        result = evaluate_plan_against_fixture(plan, fixture, fixture_path=str(fixture_path))

        self.assertTrue(result["passed"], result)
        self.assertTrue(all(assertion["passed"] for assertion in result["assertions"]))
        _run_fixture_assertions(plan, fixture)

    def test_task52_visible_question_count_assertion_rejects_dropped_questions(self):
        fixture_path = FIXTURE_ROOT / "math" / "pythagorean-alpha-beta-one-day-10q.json"
        fixture = load_fixture(fixture_path)
        plan = _pythagorean_one_day_10q_plan()
        plan["practice_tasks"] = plan["practice_tasks"][:-1]

        with self.assertRaisesRegex(AssertionError, "visible_question_count_equals"):
            _run_fixture_assertions(plan, _only_assertion(fixture, "visible_question_count_equals"))

    def test_task52_renderer_assertion_rejects_unresolved_math_placeholder(self):
        fixture_path = FIXTURE_ROOT / "math" / "sections-questions-normalization.json"
        fixture = load_fixture(fixture_path)
        plan = dynamic_geometry_source_brief_plan()
        plan["days"][0]["blanks"][0]["text"] = "公式 {{math:missing}} 对应的结论是______。"

        with self.assertRaisesRegex(AssertionError, "renderer_has_no_dropped_items"):
            _run_fixture_assertions(plan, _only_assertion(fixture, "renderer_has_no_dropped_items"))

    def test_task52_source_pack_assertion_rejects_missing_math_extraction(self):
        fixture_path = FIXTURE_ROOT / "math" / "formula-transport.json"
        fixture = load_fixture(fixture_path)
        fixture = copy.deepcopy(fixture)
        fixture["input"]["summary_text"] = "主题：课堂复习\n重点：只做普通文字整理。"
        plan = valid_plan_v1()

        with self.assertRaisesRegex(AssertionError, "source_pack_has_math_blocks"):
            _run_fixture_assertions(plan, _only_assertion(fixture, "source_pack_has_math_blocks"))

    def test_task52_source_pack_trace_assertion_rejects_raw_text_leak(self):
        fixture_path = FIXTURE_ROOT / "math" / "regeneration-same-source.json"
        fixture = load_fixture(fixture_path)
        fixture = copy.deepcopy(fixture)
        fixture["assertions"] = [
            {
                "name": "source_pack_no_raw_text_in_trace_payload",
                "notContainsAny": ["source_pack_parser_v2"],
            }
        ]
        plan = valid_plan_v1()

        with self.assertRaisesRegex(AssertionError, "source_pack_no_raw_text_in_trace_payload"):
            _run_fixture_assertions(plan, fixture)

    def test_workflow_kwargs_from_fixture_preserves_subject_context(self):
        fixture_path = FIXTURE_ROOT / "physics" / "mechanics-electricity-units-experiment.json"
        fixture = load_fixture(fixture_path)

        kwargs = workflow_kwargs_from_fixture(fixture, provider="deepseek", model="deepseek-v4-pro")

        self.assertEqual(kwargs["subject"], "physics")
        self.assertEqual(kwargs["grade"], "九年级")
        self.assertIn("中国初中物理", kwargs["summary_text"])
        self.assertIn("力学受力分析", kwargs["weak_points"])
        self.assertTrue(kwargs["include_usage"])

    def test_workflow_eval_uses_generator_and_evaluates_plan(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)
        calls = []

        def fake_generator(**kwargs):
            calls.append(kwargs)
            return valid_single_lesson_plan(subject="数学", topic="一次函数"), {
                "provider": "fake",
                "model": "fake-model",
                "input_tokens": 1,
                "output_tokens": 2,
            }

        result = run_workflow_for_fixture(fixture, fixture_path=str(fixture_path), generator=fake_generator)

        self.assertTrue(result["passed"], result)
        self.assertEqual(result["status"], "evaluated")
        self.assertEqual(result["usage"]["provider"], "fake")
        self.assertEqual(calls[0]["subject"], "math")
        self.assertTrue(result["evaluation"]["passed"])

    def test_workflow_eval_collects_filtered_fixture_report(self):
        def fake_generator(**kwargs):
            return valid_single_lesson_plan(subject="数学", topic="一次函数"), {}

        report = run_workflow_eval(
            fixture_filters=["math/algebra-weakness-6-week.json"],
            generator=fake_generator,
        )

        self.assertTrue(report["passed"], report)
        self.assertEqual(report["fixture_count"], 1)
        self.assertEqual(report["mode"], "workflow")
        self.assertEqual(report["results"][0]["status"], "evaluated")

    def test_workflow_eval_returns_generation_error_without_crashing(self):
        fixture_path = FIXTURE_ROOT / "math" / "algebra-weakness-6-week.json"
        fixture = load_fixture(fixture_path)

        def failing_generator(**kwargs):
            raise RuntimeError("missing api key")

        result = run_workflow_for_fixture(fixture, fixture_path=str(fixture_path), generator=failing_generator)

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "generation_failed")
        self.assertIn("missing api key", result["error"])


if __name__ == "__main__":
    unittest.main()
