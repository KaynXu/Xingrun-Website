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
        lesson_manager.DB_PATH = self.base / "lessons.db"
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

    def test_api_lessons_uses_review_template_generator(self):
        token = self.owner_token()

        with patch("app.has_api_key", return_value=True), \
             patch("ai_processor.parse_and_generate_plan", return_value=copy.deepcopy(DEMO_PLAN)), \
             patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf") as generate_pdf:
            generate_pdf.return_value = str(self.base / "api-review-plan.pdf")

            response = self.client.post(
                "/api/lessons",
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


if __name__ == "__main__":
    unittest.main()