from __future__ import annotations

import base64
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from reportlab.platypus import Paragraph, Table

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_processor
import pdf_engine


SAMPLE_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0ioAAAAASUVORK5CYII="
)


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

    def test_generate_student_wrong_question_library_pdf_fetches_geometry_image(self):
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "六年级 1 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 1,
                "question_text": "",
                "image_url": "https://files.example.com/geometry-1.png",
                "parent_note": "辅助线总画错",
                "teacher_comment": "先看图再讲角度关系",
            }
        ]
        output_path = self.base / "geometry-student-1.pdf"

        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = SAMPLE_PNG_BYTES

            result = pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                records=records,
                output_path=str(output_path),
            )

        self.assertEqual(result, str(output_path.resolve()))
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)
        urlopen.assert_called_once_with("https://files.example.com/geometry-1.png", timeout=10)

    def test_generate_student_wrong_question_library_pdf_skips_image_fetch_for_non_geometry(self):
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "六年级 1 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 0,
                "question_text": "计算 18÷3×2 的结果。",
                "image_url": "https://files.example.com/non-geometry-1.png",
                "parent_note": "总把顺序算反",
                "teacher_comment": "先做同级运算复盘",
            }
        ]
        output_path = self.base / "non-geometry-student-1.pdf"

        with patch("urllib.request.urlopen") as urlopen:
            result = pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                records=records,
                output_path=str(output_path),
            )

        self.assertEqual(result, str(output_path.resolve()))
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)
        urlopen.assert_not_called()

    def test_build_wrong_question_geometry_image_card_uses_fixed_box_and_caption(self):
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = SAMPLE_PNG_BYTES

            card = pdf_engine._build_wrong_question_geometry_image_card(
                "https://files.example.com/geometry-1.png",
                pdf_engine._make_styles(),
            )

        self.assertIsInstance(card, Table)
        self.assertEqual(len(card._cellvalues), 3)
        self.assertEqual(card._argW[0], pdf_engine.CONTENT_W)
        self.assertEqual(card._cellvalues[0][0].getPlainText(), "几何原题图片")
        self.assertEqual(card._cellvalues[2][0].getPlainText(), "保留原图入库，便于按图复盘几何关系。")

    def test_build_wrong_question_geometry_image_card_keeps_placeholder_when_image_unavailable(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            card = pdf_engine._build_wrong_question_geometry_image_card(
                "https://files.example.com/geometry-1.png",
                pdf_engine._make_styles(),
            )

        self.assertIsInstance(card, Table)
        self.assertEqual(len(card._cellvalues), 3)
        self.assertIsInstance(card._cellvalues[1][0], Paragraph)
        self.assertEqual(card._cellvalues[1][0].getPlainText(), "图片暂时无法载入，已保留原图记录。")

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