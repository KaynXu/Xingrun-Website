import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module
import config_runtime
import lesson_manager
from app import app
from demo_plan import DEMO_PLAN


class SingleLessonPdfUnificationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

        self.original_pdf_dir = app_module.PDF_DIR
        self.original_upload_dir = app_module.UPLOAD_DIR
        app_module.PDF_DIR = self.base / "pdfs"
        app_module.UPLOAD_DIR = self.base / "uploads"
        app_module.PDF_DIR.mkdir(parents=True, exist_ok=True)
        app_module.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        app_module.PDF_DIR = self.original_pdf_dir
        app_module.UPLOAD_DIR = self.original_upload_dir
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def owner_token(self) -> str:
        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        return login.get_json()["token"]

    def test_generate_single_lesson_pdf_creates_non_empty_pdf(self):
        from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf

        output_path = self.base / "single-lesson.pdf"
        result = generate_single_lesson_pdf(copy.deepcopy(DEMO_PLAN), str(output_path))

        self.assertEqual(Path(result), output_path.resolve())
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)

    def test_adapt_plan_to_review_template_normalizes_wechat_unstable_symbols(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan_data = {
            "lesson_info": {
                "topic": "光学与机械波",
                "key_categories": ["① 折射率与全反射", "☐ 干涉", "机械波→图像判断"],
            },
            "days": [
                {
                    "day": 1,
                    "theme": "✅ 第1天复盘",
                    "items": [
                        {"type": "body", "text": "📝 [填空题·折射率]"},
                        {"type": "fill", "text": "☐ 折射率公式→____", "answer": "n=c/v"},
                        {"type": "body", "text": "👩‍🏫 老师问：为什么进入高折射率介质后波长变短？"},
                        {"type": "body", "text": "📌 先抓频率不变"},
                    ],
                    "self_test_phrase": "⚠️ 易错点：别把质点振动当成随波迁移",
                }
            ],
        }

        lesson, days, reminders = adapt_plan_to_review_template(plan_data)

        self.assertEqual(reminders[0], "每一个复习日都要完整复习整节课内容。")
        self.assertEqual(lesson["full_review_topics"], ["1. 折射率与全反射", "[ ] 干涉", "机械波->图像判断"])
        self.assertEqual(days[0]["focus"], "[已完成] 第1天复盘")
        self.assertEqual(days[0]["tasks"][0], "题型 [填空题·折射率]")
        self.assertEqual(days[0]["tasks"][1], "老师问：为什么进入高折射率介质后波长变短？")
        self.assertEqual(days[0]["tasks"][2], "提示：先抓频率不变")
        self.assertEqual(days[0]["blanks"][0], ("[ ] 折射率公式->____", "n=c/v"))
        self.assertEqual(days[0]["quotes"], ["注意：易错点：别把质点振动当成随波迁移"])

    def test_quote_replay_text_uses_day_quotes_instead_of_static_copy(self):
        from review_plan_templates.generate_review_pdfs import build_labels, build_quote_replay_text

        labels = build_labels(True)
        day = {
            "quotes": [
                "先看图像再判断增减性。",
                "定义域先卡住，不要急着代数变形。",
            ]
        }

        replay_text = build_quote_replay_text(day, labels, True)

        self.assertIn("先看图像再判断增减性。", replay_text)
        self.assertIn("定义域先卡住，不要急着代数变形。", replay_text)
        self.assertNotEqual(replay_text, labels["quote_replay_text"])

    def test_quote_summary_text_uses_numbered_lines_without_bullets(self):
        from review_plan_templates.generate_review_pdfs import build_quote_summary_text

        summary_text = build_quote_summary_text([
            "出发口令：分类讨论，步步清晰！",
            "课堂原话回放：分类讨论的关键是有序思考，确保不重不漏。",
        ], True)

        self.assertIn("1. “出发口令：分类讨论，步步清晰！”", summary_text)
        self.assertIn("2. “课堂原话回放：分类讨论的关键是有序思考，确保不重不漏。”", summary_text)
        self.assertNotIn("- “", summary_text)

    def test_api_lessons_uses_review_template_generator(self):
        token = self.owner_token()

        with patch("app.has_api_key", return_value=True), \
             patch("ai_processor.parse_and_generate_plan", return_value=copy.deepcopy(DEMO_PLAN)), \
             patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf") as generate_pdf:
            generate_pdf.return_value = str(self.base / "api-review-plan.pdf")

            response = self.client.post(
                "/api/review-plans",
                headers=self.auth_headers(token),
                json={
                    "date": "2026-03-29",
                    "subject": "数学",
                    "grade": "初二",
                    "topic": "一次函数",
                    "summary_text": "一次函数课堂总结",
                    "input_type": "text",
                },
            )

        self.assertEqual(response.status_code, 201)
        generate_pdf.assert_called_once()

    def test_cmd_add_uses_review_template_generator(self):
        import argparse

        with patch("ai_processor.parse_and_generate_plan", return_value=copy.deepcopy(DEMO_PLAN)), \
             patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf") as generate_pdf, \
             patch("lesson_manager._open_pdf"):
            generate_pdf.return_value = str(self.base / "cli-review-plan.pdf")
            args = argparse.Namespace(
                audio=None,
                file=None,
                text="一次函数课堂总结",
                date="2026-03-29",
                subject="数学",
                grade="初二",
                topic="一次函数",
                weak="斜率和截距容易混淆",
                no_open=True,
            )
            lesson_manager.cmd_add(args)

        generate_pdf.assert_called_once()

    def test_legacy_single_lesson_entrypoint_removed_from_pdf_engine(self):
        source = (ROOT / "pdf_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("def generate_lesson_pdf(", source)


if __name__ == "__main__":
    unittest.main()
