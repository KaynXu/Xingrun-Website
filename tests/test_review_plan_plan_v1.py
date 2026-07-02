import unittest

from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template
from review_plan_workflow.plan_v1 import validate_lesson_review_plan_v1
from review_plan_workflow.printable_questions import count_printable_questions
from review_plan_workflow.schemas import normalize_final_review_plan, validate_final_review_plan


def valid_plan_v1() -> dict:
    return {
        "schema_version": "lesson_review_plan_v1",
        "document_title": "勾股数与特殊角",
        "audience": {
            "subject": "数学",
            "grade": "六年级",
            "lesson_date": "2026-07-02",
        },
        "lesson_summary": "复习整数勾股数、根式比例和 α、β 和角推导。",
        "knowledge_map": [
            {"id": "k1", "title": "整数勾股数", "summary": "熟记 3:4:5、5:12:13 等。"},
            {"id": "k2", "title": "特殊直角三角形", "summary": "掌握 1:1:√2 和 1:√3:2。"},
            {"id": "k3", "title": "α+β=45°", "summary": "能复述构造和比例推导。"},
        ],
        "review_schedule": [
            {
                "day": 1,
                "label": "当天课后复习",
                "focus": "用 10 道题检查勾股数和特殊角推导。",
                "time_minutes": 35,
                "actions": ["先背诵基础比例，再完成题目。"],
                "outputs": ["订正错题并标出错因。"],
            }
        ],
        "practice_tasks": [
            {
                "id": "b1",
                "day": 1,
                "task_type": "blank",
                "question": f"第{i}题：勾股定理等式为______。",
                "answer": "$a^2+b^2=c^2$",
                "knowledge_ids": ["k1"],
            }
            for i in range(1, 6)
        ]
        + [
            {
                "id": "c1",
                "day": 1,
                "task_type": "choice",
                "question": f"选择题{i}：下列哪组是勾股数？",
                "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                "answer": "A",
                "knowledge_ids": ["k1"],
            }
            for i in range(1, 5)
        ],
        "self_check_questions": [
            {
                "id": "s1",
                "day": 1,
                "question": "α+β 等于多少度？",
                "answer": "45°",
            }
        ],
        "math_blocks": [{"id": "pythagorean", "latex": "a^2+b^2=c^2", "display": True}],
        "teacher_checkpoints": [{"id": "t1", "text": "基础比例必须脱口而出。"}],
        "uncertainties": ["若课堂还补充了作业题，需老师追加。"],
        "source_coverage": [{"source_segment_id": "seg-1", "covered_by": ["k1", "b1"]}],
    }


class ReviewPlanV1TestCase(unittest.TestCase):
    def test_plan_v1_validates_and_adapts_to_existing_renderer_contract(self):
        plan = valid_plan_v1()

        parsed, errors = validate_lesson_review_plan_v1(plan)
        self.assertIsNotNone(parsed)
        self.assertEqual(errors, [])

        final_plan, final_errors = validate_final_review_plan(plan)
        normalized = normalize_final_review_plan(plan)
        counts = count_printable_questions(plan)
        _lesson, days, _reminders = adapt_plan_to_review_template(plan)

        self.assertIsNotNone(final_plan)
        self.assertEqual(final_errors, [])
        self.assertEqual(normalized["lesson_info"]["topic"], "勾股数与特殊角")
        self.assertEqual(counts.total_visible_questions, 10)
        self.assertEqual(len(days[0]["blanks"]) + len(days[0]["choices"]), 10)

    def test_plan_v1_rejects_wrapped_legacy_plan_shape(self):
        parsed, errors = validate_lesson_review_plan_v1({"plan": valid_plan_v1()})

        self.assertIsNone(parsed)
        self.assertTrue(errors)

    def test_plan_v1_rejects_missing_task_answer(self):
        plan = valid_plan_v1()
        plan["practice_tasks"][0]["answer"] = ""

        parsed, errors = validate_lesson_review_plan_v1(plan)

        self.assertIsNone(parsed)
        self.assertTrue(any("answer" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
