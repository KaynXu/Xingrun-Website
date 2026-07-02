import unittest

from review_plan_workflow.printable_questions import count_printable_questions


class ReviewPlanPrintableQuestionTestCase(unittest.TestCase):
    def test_count_printable_questions_dedupes_visible_questions(self):
        plan = {
            "lesson_info": {"subject": "数学", "topic": "一次函数"},
            "days": [
                {
                    "day": 1,
                    "blanks": [
                        {"text": "一次函数图像斜率由______决定。", "answer": "k"},
                        {"text": "一次函数图像斜率由______决定。", "answer": "k"},
                        {"text": "与 y 轴交点由______决定。", "answer": "b"},
                    ],
                    "choices": [
                        {
                            "question": "k>0 时图像大致如何？",
                            "options": ["A. 上升", "B. 下降", "C. 水平", "D. 竖直"],
                            "answer": "A",
                        },
                        {
                            "question": "k>0 时图像大致如何？",
                            "options": ["A. 上升", "B. 下降", "C. 水平", "D. 竖直"],
                            "answer": "A",
                        },
                    ],
                }
            ],
        }

        counts = count_printable_questions(plan)

        self.assertEqual(counts.total_visible_questions, 3)
        self.assertEqual(counts.total_answer_items, 3)
        self.assertEqual(counts.per_day[0].raw_fill_count, 3)
        self.assertEqual(counts.per_day[0].raw_choice_count, 2)
        self.assertTrue(any(item.startswith("duplicate_fill") for item in counts.dropped_items))
        self.assertTrue(any(item.startswith("duplicate_choice") for item in counts.dropped_items))


if __name__ == "__main__":
    unittest.main()
