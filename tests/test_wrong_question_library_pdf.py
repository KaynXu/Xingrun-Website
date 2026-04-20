from __future__ import annotations

import base64
import json
import subprocess
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
            }
        ]
        output_path = self.base / "student-1.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake wrong question pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("pdf_engine.subprocess.run", side_effect=fake_run):
            result = pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                records=records,
                output_path=str(output_path),
            )

        self.assertEqual(result, str(output_path.resolve()))
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)
        self.assertEqual(captured_payloads[0]["studentName"], "Alice")
        self.assertEqual(captured_payloads[0]["className"], "六年级 1 班")
        self.assertEqual(captured_payloads[0]["teacherTitle"], "平台管理员")
        self.assertEqual(captured_payloads[0]["records"][0]["question_text"], "计算 $2+3\\times4$ 的结果。")
        self.assertEqual(captured_payloads[0]["records"][0]["image_data_url"], "")

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
            }
        ]
        output_path = self.base / "geometry-student-1.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake geometry pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("urllib.request.urlopen") as urlopen, patch("pdf_engine.subprocess.run", side_effect=fake_run):
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
        self.assertRegex(captured_payloads[0]["records"][0]["image_data_url"], r"^data:image/png;base64,")

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
            }
        ]
        output_path = self.base / "non-geometry-student-1.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake non-geometry pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("urllib.request.urlopen") as urlopen, patch("pdf_engine.subprocess.run", side_effect=fake_run):
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
        self.assertEqual(captured_payloads[0]["records"][0]["image_data_url"], "")

    def test_generate_student_wrong_question_library_pdf_passes_teacher_title_once_to_browser_renderer(self):
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "六年级 1 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 0,
                "question_text": "计算 18÷3×2 的结果。",
                "image_url": "https://files.example.com/non-geometry-1.png",
            }
        ]
        output_path = self.base / "teacher-in-title-student-1.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake teacher title pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("pdf_engine.subprocess.run", side_effect=fake_run):
            pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                records=records,
                output_path=str(output_path),
            )

        self.assertEqual(captured_payloads[0]["teacherTitle"], "平台管理员")
        self.assertEqual(captured_payloads[0]["records"][0]["question_text"], "计算 18÷3×2 的结果。")

    def test_generate_student_wrong_question_library_pdf_passes_child_reason_and_note_to_browser_renderer(self):
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "六年级 1 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 0,
                "question_text": "计算 18÷3×2 的结果。",
                "child_raw_reason_text": "我把乘法放到最后算了",
                "secondary_error_summary": "运算顺序放错了位置",
            }
        ]
        output_path = self.base / "reason-and-note-student-1.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake reason and note pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("pdf_engine.subprocess.run", side_effect=fake_run):
            pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                records=records,
                output_path=str(output_path),
            )

        self.assertEqual(captured_payloads[0]["records"][0]["child_reason_text"], "我把乘法放到最后算了")
        self.assertEqual(captured_payloads[0]["records"][0]["cause_note"], "运算顺序放错了位置")

    def test_generate_student_wrong_question_library_pdf_falls_back_to_reportlab_when_browser_render_fails(self):
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "六年级 1 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 0,
                "question_text": "计算 $2+3\\times4$ 的结果。",
            }
        ]
        output_path = self.base / "fallback-student-1.pdf"

        with patch(
            "pdf_engine.subprocess.run",
            return_value=subprocess.CompletedProcess(["node"], 1, "", "browser unavailable"),
        ):
            result = pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                records=records,
                output_path=str(output_path),
            )

        self.assertEqual(result, str(output_path.resolve()))
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)

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

    def test_recognize_wrong_question_image_preserves_line_breaks_for_mixed_latex_text(self):
        normalized = ai_processor._normalize_wrong_question_recognition_result(
            {
                "is_geometry": False,
                "question_text": "解方程：\r\n$$x^2 + 1 = 0$$\r\n求 x 的值。",
                "confidence": "high",
                "notes": "",
            }
        )

        self.assertEqual(normalized["question_text"], "解方程：\n$$x^2 + 1 = 0$$\n求 x 的值。")

    def test_recognize_wrong_question_image_repairs_json_consumed_latex_backslashes(self):
        normalized = ai_processor._normalize_wrong_question_recognition_result(
            {
                "is_geometry": False,
                "question_text": "The function $f$ is continuous at $x = 3$.\n$$f(3) = 1 + \text{lim}_{x \to 3^-} f(x) + \frac{1}{2}$$\n(C) $f(3) \neq \text{lim}_{x \to 3} f(x)$",
                "confidence": "high",
                "notes": "",
            }
        )

        self.assertIn("\\text{lim}_{x \\to 3^-}", normalized["question_text"])
        self.assertIn("\\frac{1}{2}", normalized["question_text"])
        self.assertIn("\\neq \\text{lim}_{x \\to 3}", normalized["question_text"])

    def test_build_portable_wrong_question_text_repairs_broken_latex_for_reportlab_fallback(self):
        portable = pdf_engine._build_portable_wrong_question_text(
            "The function $f$ is continuous at $x = 3$.\n$$f(3) = 1 + \text{lim}_{x \to 3^-} f(x)$$\n(C) $f(3) \neq \text{lim}_{x \to 3} f(x)$"
        )

        self.assertNotIn("\t", portable)
        self.assertNotIn("ext{", portable)
        self.assertIn("lim(x → 3⁻)", portable)
        self.assertIn("f(3)≠lim(x → 3)", portable)

    def test_build_portable_wrong_question_text_normalizes_bare_latex_fragments_outside_math_delimiters(self):
        portable = pdf_engine._build_portable_wrong_question_text(
            "已知函数 f(x)=(x-1)e^{-ax}（a \\in \\mathbbR），e=2.71828\\ldots (2) 若 a>e，证明：存在实数 m 使得方程 |f(x)|=m 恰有三个不同的根，且 a<m<a\\frac{a+e}{ae}-1。"
        )

        self.assertNotIn("\\in", portable)
        self.assertNotIn("\\mathbb", portable)
        self.assertNotIn("\\ldots", portable)

    def test_generate_wrong_question_practice_sheet_pdf_requires_browser_render(self):
        items = [
            {
                "question_order": 1,
                "wrong_question_record_id": "wechat-1",
                "is_geometry": 0,
                "question_text_snapshot": "计算 $2+3\\times4$ 的结果。",
                "reason_blank_prompt": "先梳理错因\n这道题因为 ______ 所以做错了，还漏看了 ______，相关知识点是 ______。",
                "improvement_summary_prompt": "再写你的想法\n接下来我准备先补 ______，再练 ______，做题时提醒自己注意 ______。",
            }
        ]
        output_path = self.base / "practice-browser-required.pdf"

        with patch(
            "pdf_engine.subprocess.run",
            return_value=subprocess.CompletedProcess(["node"], 1, "", "browser unavailable"),
        ):
            with self.assertRaises(RuntimeError) as context:
                pdf_engine.generate_wrong_question_practice_sheet_pdf(
                    student_name="Alice",
                    class_name="六年级 1 班",
                    teacher_name="平台管理员",
                    title="Alice 错题练习",
                    items=items,
                    output_path=str(output_path),
                )

        self.assertIn("browser unavailable", str(context.exception))
        self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
