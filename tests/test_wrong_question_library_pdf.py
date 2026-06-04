from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from PIL import Image as PILImage
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

    def test_generate_student_wrong_question_library_pdf_prefers_structured_geometry_diagram(self):
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "六年级 1 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 1,
                "question_text": "如图，数轴上点 A 表示 -5，点 B 表示 15。",
                "image_url": "https://files.example.com/geometry-original.png",
                "diagram_type": "number_line",
                "diagram_spec": {
                    "type": "number_line",
                    "points": [
                        {"label": "A", "value": -5},
                        {"label": "B", "value": 15},
                    ],
                },
            }
        ]
        output_path = self.base / "structured-geometry-student-1.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake structured geometry pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("urllib.request.urlopen") as urlopen, patch("pdf_engine.subprocess.run", side_effect=fake_run):
            pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                records=records,
                output_path=str(output_path),
            )

        normalized_record = captured_payloads[0]["records"][0]
        urlopen.assert_not_called()
        self.assertEqual(normalized_record["question_text"], "如图，数轴上点 A 表示 -5，点 B 表示 15。")
        self.assertEqual(normalized_record["diagram_type"], "number_line")
        self.assertRegex(normalized_record["image_data_url"], r"^data:image/svg\+xml;base64,")
        decoded_svg = base64.b64decode(normalized_record["image_data_url"].split(",", 1)[1]).decode("utf-8")
        self.assertIn("<svg", decoded_svg)
        self.assertIn(">A<", decoded_svg)
        self.assertIn(">B<", decoded_svg)

    def test_structured_geometry_diagram_preserves_square_aspect_ratio(self):
        svg = pdf_engine._render_wrong_question_geometry_svg(
            {
                "type": "geometry",
                "points": [
                    {"label": "A", "x": -1, "y": 1},
                    {"label": "B", "x": 1, "y": 1},
                    {"label": "C", "x": 1, "y": -1},
                    {"label": "D", "x": -1, "y": -1},
                ],
                "segments": [
                    {"from": "A", "to": "B"},
                    {"from": "B", "to": "C"},
                ],
            }
        )
        segment_lines = [
            tuple(float(value) for value in match.groups())
            for match in re.finditer(
                r'<line x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)"',
                svg,
            )
        ]
        self.assertEqual(len(segment_lines), 2)
        ab = ((segment_lines[0][2] - segment_lines[0][0]) ** 2 + (segment_lines[0][3] - segment_lines[0][1]) ** 2) ** 0.5
        bc = ((segment_lines[1][2] - segment_lines[1][0]) ** 2 + (segment_lines[1][3] - segment_lines[1][1]) ** 2) ** 0.5
        self.assertAlmostEqual(ab, bc, delta=0.5)

    def test_generate_student_wrong_question_library_pdf_renders_function_plot_for_non_geometry_record(self):
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "八年级 2 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 0,
                "question_text": "如图，抛物线经过点 $(-1,1)$、$(0,0)$、$(1,1)$。",
                "image_url": "https://files.example.com/function-original.png",
                "diagram_type": "function_plot",
                "diagram_spec_json": json.dumps(
                    {
                        "type": "function_plot",
                        "x_min": -2,
                        "x_max": 2,
                        "y_min": -1,
                        "y_max": 4,
                        "curves": [
                            {
                                "label": "y=x^2",
                                "points": [
                                    [-2, 4],
                                    [-1, 1],
                                    [0, 0],
                                    [1, 1],
                                    [2, 4],
                                ],
                            }
                        ],
                    }
                ),
            }
        ]
        output_path = self.base / "function-plot-student-1.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake function plot pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("urllib.request.urlopen") as urlopen, patch("pdf_engine.subprocess.run", side_effect=fake_run):
            pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="八年级 2 班",
                records=records,
                output_path=str(output_path),
            )

        normalized_record = captured_payloads[0]["records"][0]
        urlopen.assert_not_called()
        self.assertEqual(normalized_record["diagram_type"], "function_plot")
        self.assertRegex(normalized_record["image_data_url"], r"^data:image/svg\+xml;base64,")
        decoded_svg = base64.b64decode(normalized_record["image_data_url"].split(",", 1)[1]).decode("utf-8")
        self.assertIn("<svg", decoded_svg)
        self.assertIn("<path", decoded_svg)
        self.assertNotIn("<polyline", decoded_svg)
        self.assertIn("y=x^2", decoded_svg)

    def test_generate_student_wrong_question_library_pdf_rotates_geometry_image_data_url(self):
        source_image = PILImage.new("RGB", (2, 1), "white")
        source_buffer = io.BytesIO()
        source_image.save(source_buffer, format="PNG")
        records = [
            {
                "student_name": "Alice",
                "class_display_name": "六年级 1 班",
                "teacher_display_name": "平台管理员",
                "created_at": "2026-04-09 10:00:00",
                "is_geometry": 1,
                "question_text": "",
                "image_url": "https://files.example.com/geometry-rotated.png",
                "image_rotation_degrees": 90,
            }
        ]
        output_path = self.base / "geometry-rotated-student-1.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake rotated geometry pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("urllib.request.urlopen") as urlopen, patch("pdf_engine.subprocess.run", side_effect=fake_run):
            urlopen.return_value.__enter__.return_value.read.return_value = source_buffer.getvalue()

            pdf_engine.generate_student_wrong_question_library_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                records=records,
                output_path=str(output_path),
            )

        data_url = captured_payloads[0]["records"][0]["image_data_url"]
        encoded_bytes = data_url.split(",", 1)[1]
        rotated = PILImage.open(io.BytesIO(base64.b64decode(encoded_bytes)))
        self.assertEqual(rotated.size, (1, 2))

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

    def test_recognize_wrong_question_image_normalizes_rotation_degrees(self):
        geometry = ai_processor._normalize_wrong_question_recognition_result(
            {
                "is_geometry": True,
                "question_text": "如图，菱形 ABCD 的对角线相交于点 O。",
                "confidence": "high",
                "notes": "",
                "image_rotation_degrees": 90,
                "diagram_type": "geometry",
                "diagram_spec": {
                    "type": "geometry",
                    "points": [{"label": "A", "x": 0, "y": 1}],
                    "segments": [],
                },
            }
        )
        non_geometry = ai_processor._normalize_wrong_question_recognition_result(
            {
                "is_geometry": False,
                "question_text": "计算 $1+1$。",
                "confidence": "high",
                "notes": "",
                "image_rotation_degrees": 45,
            }
        )

        self.assertEqual(geometry["image_rotation_degrees"], 90)
        self.assertEqual(geometry["question_text"], "如图，菱形 ABCD 的对角线相交于点 O。")
        self.assertEqual(geometry["diagram_type"], "geometry")
        self.assertEqual(geometry["diagram_spec"]["type"], "geometry")
        self.assertEqual(non_geometry["image_rotation_degrees"], 0)

    def test_recognize_wrong_question_image_preserves_function_diagram_spec(self):
        normalized = ai_processor._normalize_wrong_question_recognition_result(
            {
                "is_geometry": False,
                "question_text": "如图，函数 $y=x^2$ 经过原点。",
                "confidence": "high",
                "notes": "",
                "diagram_type": "function_plot",
                "diagram_spec": {
                    "type": "function_plot",
                    "curves": [{"points": [[-1, 1], [0, 0], [1, 1]]}],
                },
            }
        )

        self.assertEqual(normalized["diagram_type"], "function_plot")
        self.assertEqual(normalized["diagram_spec"]["type"], "function_plot")

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

    def test_recognize_wrong_question_image_rewrites_until_ai_quality_review_passes(self):
        attempts = [
            {
                "is_geometry": False,
                "question_text": "学生写：答案是 3。原题：计算 x^2+1。",
                "confidence": "high",
                "notes": "",
            },
            {
                "is_geometry": False,
                "question_text": "计算 $x^2+1$ 的值。",
                "confidence": "high",
                "notes": "",
            },
        ]
        reviews = [
            "结论：不通过\n问题：包含学生手写答案。",
            "结论：通过\n问题：无",
        ]

        with patch("ai_processor._request_wrong_question_recognition_attempt", side_effect=attempts) as recognize, \
            patch("ai_processor._review_wrong_question_recognition_quality", side_effect=reviews) as review, \
            patch("ai_processor._collect_wrong_question_latex_render_issues", return_value=[]):
            result = ai_processor.recognize_wrong_question_image("https://files.example.com/question.png")

        self.assertEqual(result["question_text"], "计算 $x^2+1$ 的值。")
        self.assertEqual(recognize.call_count, 2)
        self.assertEqual(review.call_count, 2)
        self.assertIn("包含学生手写答案", recognize.call_args_list[1].kwargs["revision_feedback"])

    def test_recognize_wrong_question_image_stops_after_limited_failed_reviews(self):
        attempt = {
            "is_geometry": False,
            "question_text": "学生写：答案是 3。原题：计算 x^2+1。",
            "confidence": "high",
            "notes": "",
        }

        with patch("ai_processor._request_wrong_question_recognition_attempt", return_value=attempt) as recognize, \
            patch(
                "ai_processor._review_wrong_question_recognition_quality",
                return_value="结论：不通过\n问题：包含学生手写答案。",
            ), \
            patch("ai_processor._collect_wrong_question_latex_render_issues", return_value=[]):
            with self.assertRaises(ValueError) as context:
                ai_processor.recognize_wrong_question_image("https://files.example.com/question.png")

        self.assertEqual(recognize.call_count, 3)
        self.assertIn("题目识别质量检查未通过", str(context.exception))

    def test_recognize_wrong_question_image_rewrites_when_latex_render_check_fails(self):
        attempts = [
            {
                "is_geometry": False,
                "question_text": "计算 $\\frac{1}{$ 的值。",
                "confidence": "high",
                "notes": "",
            },
            {
                "is_geometry": False,
                "question_text": "计算 $\\frac{1}{2}$ 的值。",
                "confidence": "high",
                "notes": "",
            },
        ]

        with patch("ai_processor._request_wrong_question_recognition_attempt", side_effect=attempts) as recognize, \
            patch("ai_processor._review_wrong_question_recognition_quality", return_value="结论：通过\n问题：无"), \
            patch(
                "ai_processor._collect_wrong_question_latex_render_issues",
                side_effect=[["Expected group after '\\frac'"], []],
            ):
            result = ai_processor.recognize_wrong_question_image("https://files.example.com/question.png")

        self.assertEqual(result["question_text"], "计算 $\\frac{1}{2}$ 的值。")
        self.assertEqual(recognize.call_count, 2)
        self.assertIn("LaTeX 渲染检查未通过", recognize.call_args_list[1].kwargs["revision_feedback"])

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

    def test_build_portable_wrong_question_text_normalizes_indexed_roots_for_reportlab_fallback(self):
        portable = pdf_engine._build_portable_wrong_question_text(
            "计算 \\sqrt[3]{8} + $\\sqrt[4]{16}+x_1^2$，且 a \\in \\mathbb{R}。"
        )

        self.assertIn("³√(8)", portable)
        self.assertIn("⁴√(16)", portable)
        self.assertIn("x₁²", portable)
        self.assertIn("∈ ℝ", portable)
        self.assertNotIn("\\sqrt", portable)

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

    def test_generate_wrong_question_practice_sheet_pdf_surfaces_exit_code_when_renderer_outputs_nothing(self):
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
        output_path = self.base / "practice-browser-exit-code.pdf"

        with patch(
            "pdf_engine.subprocess.run",
            return_value=subprocess.CompletedProcess(["node"], 137, "", ""),
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

        self.assertIn("exit code 137", str(context.exception))
        self.assertFalse(output_path.exists())

    def test_generate_wrong_question_practice_sheet_pdf_sanitizes_browser_environment(self):
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
        output_path = self.base / "practice-browser-env.pdf"
        captured_env = {}

        def fake_run(command, **kwargs):
            captured_env.update(kwargs.get("env") or {})
            Path(command[3]).write_bytes(b"%PDF-1.4 fake practice pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch.dict(
            os.environ,
            {
                "PATH": "/usr/local/bin:/usr/bin",
                "HOME": "/home/ubuntu",
                "LANG": "zh_CN.UTF-8",
                "XDG_RUNTIME_DIR": "/run/user/1000",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                "XR_PLAYWRIGHT_EXECUTABLE_PATH": "/snap/bin/chromium",
                "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH": "/custom/chromium",
                "PLAYWRIGHT_BROWSERS_PATH": "/home/ubuntu/.cache/ms-playwright",
                "NODE_CHANNEL_FD": "3",
                "PM2_HOME": "/home/ubuntu/.pm2",
                "axm_options": "{}",
                "status": "launching",
                "env": "[object Object]",
            },
            clear=True,
        ):
            with patch("pdf_engine.subprocess.run", side_effect=fake_run):
                result = pdf_engine.generate_wrong_question_practice_sheet_pdf(
                    student_name="Alice",
                    class_name="六年级 1 班",
                    teacher_name="平台管理员",
                    title="Alice 错题练习",
                    items=items,
                    output_path=str(output_path),
                )

        self.assertEqual(result, str(output_path.resolve()))
        self.assertEqual(captured_env["PATH"], "/usr/local/bin:/usr/bin")
        self.assertEqual(captured_env["HOME"], "/home/ubuntu")
        self.assertEqual(captured_env["LANG"], "zh_CN.UTF-8")
        self.assertEqual(captured_env["XR_PLAYWRIGHT_EXECUTABLE_PATH"], "/snap/bin/chromium")
        self.assertEqual(captured_env["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"], "/custom/chromium")
        self.assertEqual(captured_env["PLAYWRIGHT_BROWSERS_PATH"], "/home/ubuntu/.cache/ms-playwright")
        self.assertNotIn("NODE_CHANNEL_FD", captured_env)
        self.assertNotIn("PM2_HOME", captured_env)
        self.assertNotIn("axm_options", captured_env)
        self.assertNotIn("status", captured_env)
        self.assertNotIn("env", captured_env)

    def test_generate_wrong_question_practice_sheet_pdf_passes_structured_content_and_reflection_snapshots(self):
        items = [
            {
                "question_order": 1,
                "wrong_question_record_id": "wechat-1",
                "is_geometry": 0,
                "question_text_snapshot": "解方程 $\\frac{x-1}{2}=3$。",
                "reason_blank_prompt": "先复盘这题错因\n我这题错在 ______，因为 ______。",
                "improvement_summary_prompt": "再写下次提醒\n下次我会先 ______，再检查 ______。",
                "structured_content": {
                    "mistake_focus": "去分母时漏乘右边常数",
                    "teacher_feedback": "继续追问为什么右边也要同乘。",
                },
                "question_structured_snapshot_json": {
                    "stem": "解方程 (x-1)/2=3",
                    "subject": "数学",
                },
                "knowledge_tags_snapshot_json": ["一元一次方程", "去分母"],
                "reflection_summary_snapshot_json": {
                    "schema_version": "wrong_question_reflection_summary.v1",
                    "why_wrong": "我去分母时漏乘了右边常数",
                    "unknown_step": "不知道等式右边也要同乘 2",
                    "help_preference": "先提醒我要两边一起乘，再让我自己重做",
                },
            }
        ]
        output_path = self.base / "practice-reflection-payload.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake practice reflection pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("pdf_engine.subprocess.run", side_effect=fake_run):
            result = pdf_engine.generate_wrong_question_practice_sheet_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                teacher_name="平台管理员",
                title="Alice 错题练习",
                items=items,
                output_path=str(output_path),
            )

        self.assertEqual(result, str(output_path.resolve()))
        payload_item = captured_payloads[0]["items"][0]
        self.assertEqual(payload_item["structured_content"]["mistake_focus"], "去分母时漏乘右边常数")
        self.assertEqual(payload_item["structured_content"]["teacher_feedback"], "继续追问为什么右边也要同乘。")
        self.assertEqual(payload_item["question_structured_snapshot_json"]["stem"], "解方程 (x-1)/2=3")
        self.assertEqual(payload_item["knowledge_tags_snapshot_json"], ["一元一次方程", "去分母"])
        self.assertEqual(
            payload_item["reflection_summary_snapshot_json"]["help_preference"],
            "先提醒我要两边一起乘，再让我自己重做",
        )

    def test_generate_wrong_question_practice_sheet_pdf_fetches_original_image_for_non_geometry_item(self):
        items = [
            {
                "question_order": 1,
                "wrong_question_record_id": "wechat-1",
                "is_geometry": 0,
                "question_text_snapshot": "计算 18÷3×2 的结果。",
                "image_url_snapshot": "https://files.example.com/non-geometry-practice.png",
            }
        ]
        output_path = self.base / "practice-non-geometry-image.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake practice image pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("urllib.request.urlopen") as urlopen, patch("pdf_engine.subprocess.run", side_effect=fake_run):
            urlopen.return_value.__enter__.return_value.read.return_value = SAMPLE_PNG_BYTES

            result = pdf_engine.generate_wrong_question_practice_sheet_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                teacher_name="平台管理员",
                title="Alice 错题练习",
                items=items,
                output_path=str(output_path),
            )

        self.assertEqual(result, str(output_path.resolve()))
        self.assertEqual(urlopen.call_count, 2)
        urlopen.assert_any_call("https://files.example.com/non-geometry-practice.png", timeout=10)
        self.assertRegex(captured_payloads[0]["items"][0]["image_data_url"], r"^data:image/png;base64,")

    def test_generate_wrong_question_practice_sheet_pdf_prefers_erased_image_snapshot(self):
        items = [
            {
                "question_order": 1,
                "wrong_question_record_id": "wechat-1",
                "is_geometry": 0,
                "question_text_snapshot": "计算 18÷3×2 的结果。",
                "image_url_snapshot": "https://files.example.com/non-geometry-original.png",
                "erased_image_url_snapshot": "https://files.example.com/non-geometry-erased.png",
            }
        ]
        output_path = self.base / "practice-erased-image.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake practice erased image pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("urllib.request.urlopen") as urlopen, patch("pdf_engine.subprocess.run", side_effect=fake_run):
            urlopen.return_value.__enter__.return_value.read.return_value = SAMPLE_PNG_BYTES

            result = pdf_engine.generate_wrong_question_practice_sheet_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                teacher_name="平台管理员",
                title="Alice 错题练习",
                items=items,
                output_path=str(output_path),
            )

        self.assertEqual(result, str(output_path.resolve()))
        self.assertEqual(urlopen.call_count, 2)
        urlopen.assert_any_call("https://files.example.com/non-geometry-erased.png", timeout=10)
        self.assertNotIn(
            ("https://files.example.com/non-geometry-original.png",),
            [call.args for call in urlopen.call_args_list],
        )
        self.assertRegex(captured_payloads[0]["items"][0]["image_data_url"], r"^data:image/png;base64,")

    def test_generate_wrong_question_practice_sheet_pdf_reads_local_erased_image_snapshot(self):
        erased_path = self.base / "erased-question.png"
        erased_path.write_bytes(SAMPLE_PNG_BYTES)
        items = [
            {
                "question_order": 1,
                "wrong_question_record_id": "wechat-1",
                "is_geometry": 0,
                "question_text_snapshot": "计算 18÷3×2 的结果。",
                "image_url_snapshot": "https://files.example.com/non-geometry-original.png",
                "erased_image_url_snapshot": str(erased_path),
            }
        ]
        output_path = self.base / "practice-local-erased-image.pdf"
        captured_payloads = []

        def fake_run(command, **kwargs):
            payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            captured_payloads.append(payload)
            Path(command[3]).write_bytes(b"%PDF-1.4 fake local erased image pdf")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("urllib.request.urlopen") as urlopen, patch("pdf_engine.subprocess.run", side_effect=fake_run):
            result = pdf_engine.generate_wrong_question_practice_sheet_pdf(
                student_name="Alice",
                class_name="六年级 1 班",
                teacher_name="平台管理员",
                title="Alice 错题练习",
                items=items,
                output_path=str(output_path),
            )

        self.assertEqual(result, str(output_path.resolve()))
        urlopen.assert_not_called()
        self.assertRegex(captured_payloads[0]["items"][0]["image_data_url"], r"^data:image/png;base64,")


if __name__ == "__main__":
    unittest.main()
