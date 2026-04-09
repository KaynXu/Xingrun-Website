from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_processor
import pdf_engine


class WrongQuestionLibraryPdfTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_generate_student_wrong_question_library_pdf_creates_non_empty_pdf(self):
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "六年级 1 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 0,
                "question_text": "计算 $2+3\\times4$ 的结果。",
                "image_url": "https://files.example.com/question-1.png",
                "parent_note": "总是忘记先乘后加",
                "teacher_comment": "下节课先复盘运算顺序",
            }
        ]
        output_path = self.base / "student-1.pdf"

        result = pdf_engine.generate_student_wrong_question_library_pdf(
            student_name="Alice",
            class_name="六年级 1 班",
            records=records,
            output_path=str(output_path),
        )

        self.assertEqual(result, str(output_path.resolve()))
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)

    def test_recognize_wrong_question_image_rejects_blank_non_geometry_text(self):
        with self.assertRaises(ValueError):
            ai_processor._normalize_wrong_question_recognition_result(
                {
                    "is_geometry": False,
                    "question_text": "无法识别",
                    "confidence": "low",
                    "notes": "图片模糊",
                }
            )


if __name__ == "__main__":
    unittest.main()