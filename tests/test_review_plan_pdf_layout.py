import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from reportlab.lib.pagesizes import A4

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
    def test_page_header_draws_left_aligned_brand_name(self):
        generate_review_pdfs.register_fonts()
        styles = generate_review_pdfs.build_styles({"brand": {"name": "星润教育"}})

        class FakeCanvas:
            def __init__(self):
                self.draw_strings = []
                self.images = []

            def saveState(self):
                pass

            def restoreState(self):
                pass

            def setStrokeColor(self, _color):
                pass

            def setLineWidth(self, _width):
                pass

            def line(self, *_args):
                pass

            def drawImage(self, image, x, y, width, height, **_kwargs):
                self.images.append((image, x, y, width, height))

            def setFont(self, *_args):
                pass

            def setFillColor(self, _color):
                pass

            def drawString(self, x, y, text):
                self.draw_strings.append((x, y, text))

            def drawRightString(self, *_args):
                pass

            def getPageNumber(self):
                return 1

        canvas = FakeCanvas()
        doc = SimpleNamespace(leftMargin=18 * generate_review_pdfs.mm, rightMargin=18 * generate_review_pdfs.mm)

        with patch("review_plan_templates.generate_review_pdfs._resolve_brand_logo", return_value=Path("logo.png")), \
             patch("review_plan_templates.generate_review_pdfs.ImageReader", return_value=object()):
            draw = generate_review_pdfs.on_page(
                styles,
                "cn",
                style_config={"brand": {"name": "星润教育"}},
                lesson_title="测试课程",
            )
            draw(canvas, doc)

        self.assertIn("星润教育", [text for _x, _y, text in canvas.draw_strings])
        self.assertEqual(len(canvas.images), 1)
        brand_x = next(x for x, _y, text in canvas.draw_strings if text == "星润教育")
        expected_brand_x = doc.leftMargin + 8.5 * generate_review_pdfs.mm + 3 * generate_review_pdfs.mm
        self.assertAlmostEqual(brand_x, expected_brand_x)

    def test_daily_overview_keeps_tasks_without_repeating_full_coverage(self):
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

        self.assertEqual(box_titles.count(labels["coverage_title"]), 1)
        self.assertEqual(box_titles.count(labels["tasks_title"]), len(_sample_days()))

    def test_day_heading_uses_day_one_as_base_date(self):
        base_date = date(2026, 7, 2)

        day_one_heading = generate_review_pdfs.build_day_heading(
            {"offset": 1, "day": "第1天"},
            base_date,
            chinese_only=True,
        )
        day_two_heading = generate_review_pdfs.build_day_heading(
            {"offset": 2, "day": "第2天"},
            base_date,
            chinese_only=True,
        )
        day_seven_heading = generate_review_pdfs.build_day_heading(
            {"offset": 7, "day": "第7天"},
            base_date,
            chinese_only=True,
        )

        self.assertIn("日期：2026-07-02", day_one_heading)
        self.assertIn("日期：2026-07-03", day_two_heading)
        self.assertIn("日期：2026-07-08", day_seven_heading)

    def test_one_day_plan_uses_compressed_final_reminder_label(self):
        labels = generate_review_pdfs.adapt_labels_for_review_schedule(
            generate_review_pdfs.build_labels(chinese_only=True),
            [{"offset": 1, "day": "第1天集中复习"}],
            chinese_only=True,
        )

        self.assertEqual(labels["usage_text"], "集中完成本次复习：先回忆课堂主线，再完成题目和自查。")
        self.assertEqual(labels["final_reminder_box"], "本次集中复习后应留下的内容")

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

    def test_make_box_splits_long_flowable_lists_across_pages(self):
        generate_review_pdfs.register_fonts()
        styles = generate_review_pdfs.build_styles()
        body = [
            generate_review_pdfs.Paragraph(
                f"{index}. 这是一条很长的复习任务，用来撑高卡片并验证表格是否能跨页。",
                styles["body"],
            )
            for index in range(90)
        ]

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "long-box.pdf"
            doc = generate_review_pdfs.SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                leftMargin=18 * generate_review_pdfs.mm,
                rightMargin=18 * generate_review_pdfs.mm,
                topMargin=24 * generate_review_pdfs.mm,
                bottomMargin=16 * generate_review_pdfs.mm,
            )

            doc.build([generate_review_pdfs.make_box("长卡片", body, styles, styles["card"])])

            self.assertGreater(output_path.stat().st_size, 0)

    def test_make_box_does_not_turn_legacy_spacers_into_blank_rows(self):
        generate_review_pdfs.register_fonts()
        styles = generate_review_pdfs.build_styles()

        box = generate_review_pdfs.make_box(
            "测试卡片",
            [
                generate_review_pdfs.Paragraph("第一句", styles["body"]),
                generate_review_pdfs.Spacer(1, 12),
                generate_review_pdfs.Paragraph("第二句", styles["body"]),
            ],
            styles,
            styles["card"],
        )

        self.assertEqual(box._nrows, 3)

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
