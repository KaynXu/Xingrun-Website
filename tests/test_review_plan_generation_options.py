import unittest

from review_plan_workflow.generation_options import (
    generation_options_summary,
    generation_options_trace_summary,
    normalize_generation_options,
)


class ReviewPlanGenerationOptionsTestCase(unittest.TestCase):
    def test_defaults_to_standard_five_day_schedule(self):
        options = normalize_generation_options(None)

        self.assertEqual(options["schedule_mode"], "standard")
        self.assertEqual(options["review_days"], [1, 2, 7, 14, 30])
        self.assertEqual(options["daily_count"], None)
        self.assertEqual(options["user_requirements"], "")
        self.assertEqual(options["source"], "create")
        self.assertEqual(generation_options_summary(options), "5次间隔复习")

    def test_compressed_forces_single_day(self):
        options = normalize_generation_options(
            {
                "schedule_mode": "compressed",
                "review_days": [1, 2, 7],
                "user_requirements": "明天考试前冲刺",
            },
            source="regenerate",
        )

        self.assertEqual(options["schedule_mode"], "compressed")
        self.assertEqual(options["review_days"], [1])
        self.assertEqual(options["daily_count"], 1)
        self.assertEqual(options["user_requirements"], "明天考试前冲刺")
        self.assertEqual(options["source"], "regenerate")
        self.assertEqual(generation_options_summary(options), "当天课后复习")

    def test_daily_count_expands_to_consecutive_days(self):
        options = normalize_generation_options({"schedule_mode": "daily", "daily_count": 4})

        self.assertEqual(options["review_days"], [1, 2, 3, 4])
        self.assertEqual(options["daily_count"], 4)
        self.assertEqual(generation_options_summary(options), "每日连续 4 天")

    def test_custom_accepts_comma_string_sorts_and_dedupes(self):
        options = normalize_generation_options({"schedule_mode": "custom", "review_days": "7, 1, 3, 3"})

        self.assertEqual(options["review_days"], [1, 3, 7])
        self.assertEqual(options["daily_count"], None)
        self.assertEqual(generation_options_summary(options), "自定义日期 1,3,7")

    def test_rejects_zero_negative_and_more_than_30_days(self):
        for payload in (
            {"schedule_mode": "custom", "review_days": [0]},
            {"schedule_mode": "custom", "review_days": [-1]},
            {"schedule_mode": "custom", "review_days": [True]},
            {"schedule_mode": "custom", "review_days": [1.5]},
            {"schedule_mode": "daily", "daily_count": 31},
            {"schedule_mode": "daily", "daily_count": "1,2,3"},
            {"schedule_mode": "custom", "review_days": list(range(1, 32))},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    normalize_generation_options(payload)

    def test_user_requirements_are_trimmed_and_capped(self):
        options = normalize_generation_options({"user_requirements": "  " + "要求" * 600 + "  "})

        self.assertEqual(len(options["user_requirements"]), 1000)
        self.assertFalse(options["user_requirements"].startswith(" "))
        self.assertFalse(options["user_requirements"].endswith(" "))

    def test_trace_summary_does_not_expose_full_requirement_text(self):
        options = normalize_generation_options(
            {
                "schedule_mode": "standard",
                "user_requirements": "题量少一点，适合明天考试前冲刺，多给选择题诊断",
            }
        )

        trace = generation_options_trace_summary(options)

        self.assertEqual(trace["schedule_mode"], "standard")
        self.assertEqual(trace["review_days"], [1, 2, 7, 14, 30])
        self.assertEqual(trace["has_user_requirements"], True)
        self.assertIn("user_requirements_preview", trace)
        self.assertLessEqual(len(trace["user_requirements_preview"]), 40)

    def test_parses_teacher_question_count_constraint(self):
        options = normalize_generation_options(
            {
                "schedule_mode": "compressed",
                "user_requirements": "题目控制在10道题，选择题不要全是执行清单",
            }
        )

        self.assertEqual(options["constraints"]["requested_question_count"], 10)
        trace = generation_options_trace_summary(options)
        self.assertEqual(trace["requested_question_count"], 10)


if __name__ == "__main__":
    unittest.main()
