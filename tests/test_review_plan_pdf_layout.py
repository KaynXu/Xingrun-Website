import unittest
from pathlib import Path
from unittest.mock import patch

from review_plan_templates import generate_review_pdfs


def _sample_lesson():
    return {
        "title": "向量复习计划",
        "subtitle": "",
        "audience": "老师发给学生使用",
        "duration": "每次 10-20 分钟",
        "full_review_topics": ["数量积入口", "单位向量", "投影长度"],
        "quotes": ["先判断夹角，再决定公式。"],
    }


def _sample_days():
    return [
        {
            "offset": 1,
            "day": "第1天",
            "goal": "先挂起整课方法地图。",
            "focus": "全课复盘。",
            "tasks": ["扫完整课清单", "完成当天题目"],
            "blanks": [("看到数量积先看____________。", "夹角")],
            "choices": [{"question": "数量积先看什么？", "options": ["A. 夹角", "B. 页码"], "answer": "A"}],
            "quotes": ["先判断夹角，再决定公式。"],
        },
        {
            "offset": 2,
            "day": "第2天",
            "goal": "只做当天题目。",
            "focus": "方法入口巩固。",
            "tasks": ["不重复整课清单"],
            "blanks": [("单位向量坐标是____________。", "(cos θ, sin θ)")],
            "choices": [{"question": "单位向量看什么？", "options": ["A. 坐标", "B. 颜色"], "answer": "A"}],
            "quotes": ["单位向量先写坐标。"],
        },
    ]


class ReviewPlanPdfLayoutTestCase(unittest.TestCase):
    def test_daily_overview_sections_stop_after_first_review_day(self):
        generate_review_pdfs.register_fonts()
        styles = generate_review_pdfs.build_styles()
        labels = generate_review_pdfs.build_labels(chinese_only=True)
        box_titles = []
        original_make_box = generate_review_pdfs.make_box

        def record_make_box(title, body, styles_arg, background):
            box_titles.append(title)
            return original_make_box(title, body, styles_arg, background)

        with patch("review_plan_templates.generate_review_pdfs.make_box", side_effect=record_make_box):
            generate_review_pdfs.build_story(
                styles,
                "cn",
                lesson=_sample_lesson(),
                days=_sample_days(),
                final_reminder_lines=["先看入口，再写步骤。"],
                knowledge_sections={},
            )

        self.assertEqual(box_titles.count(labels["coverage_title"]), 2)
        self.assertEqual(box_titles.count(labels["tasks_title"]), 1)

    def test_answer_key_uses_compact_summary_instead_of_per_day_heading_blocks(self):
        generate_review_pdfs.register_fonts()
        styles = generate_review_pdfs.build_styles()

        story = generate_review_pdfs.build_story(
            styles,
            "cn",
            lesson=_sample_lesson(),
            days=_sample_days(),
            final_reminder_lines=["先看入口，再写步骤。"],
            knowledge_sections={},
        )

        answer_day_headings = [
            flowable.getPlainText()
            for flowable in story
            if getattr(getattr(flowable, "style", None), "name", "") == "h2"
            and "日期：" in flowable.getPlainText()
        ]

        self.assertEqual(answer_day_headings, [])

    def test_answer_key_table_uses_two_side_by_side_answer_sets(self):
        generate_review_pdfs.register_fonts()
        styles = generate_review_pdfs.build_styles()
        labels = generate_review_pdfs.build_labels(chinese_only=True)

        table = generate_review_pdfs.make_compact_answer_key_table(
            _sample_days(),
            {},
            styles,
            labels,
            "cn",
            chinese_only=True,
        )

        self.assertEqual(table._ncols, 6)

    def test_cli_output_filename_uses_lesson_knowledge_points(self):
        output_dir = Path("/tmp/review-plan-layout-test")
        with patch("sys.argv", ["generate_review_pdfs.py", "cn"]), \
             patch.object(generate_review_pdfs, "OUTPUT_DIR", output_dir), \
             patch.object(generate_review_pdfs, "LESSON", _sample_lesson()), \
             patch.object(generate_review_pdfs, "DAYS", _sample_days()), \
             patch.object(generate_review_pdfs, "FINAL_REMINDER_LINES", ["先看入口，再写步骤。"]), \
             patch.object(generate_review_pdfs, "KNOWLEDGE_SECTIONS", {}), \
             patch("review_plan_templates.generate_review_pdfs.render_review_plan_pdf") as render_pdf:
            generate_review_pdfs.main()

        output_path = Path(render_pdf.call_args.kwargs["output_path"])
        self.assertIn("数量积入口-单位向量-投影长度", output_path.name)
        self.assertNotIn("review-plan-chinese-only", output_path.name)


if __name__ == "__main__":
    unittest.main()
