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
from tests.review_plan_test_utils import components_only_single_lesson_plan, valid_single_lesson_plan, writer_style_single_lesson_plan


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

    def test_adapt_plan_to_review_template_preserves_method_map_density(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template, extract_knowledge_sections

        plan_data = {
            "lesson_info": {
                "topic": "立体几何",
                "key_categories": [f"核心主题{i}" for i in range(1, 7)],
            },
            "full_review_topics": [f"补充主题{i}" for i in range(7, 18)],
            "quotes": [f"课堂原话{i}" for i in range(1, 13)],
            "final_reminder_lines": ["先标数据", "再求法向量"],
            "days": [
                {
                    "day": 1,
                    "label": "第1天",
                    "steps": [
                        {
                            "title": "复习目标",
                            "items": [
                                {"type": "fill", "text": f"方法链填空{i}____", "answer": f"答案{i}"}
                                for i in range(1, 8)
                            ],
                        }
                    ],
                    "choices": [
                        {"question": "选择题1？", "options": ["A. 对", "B. 错", "C. 空", "D. 空"], "answer": "A"},
                        {"question": "选择题2？", "options": ["A. 错", "B. 对", "C. 空", "D. 空"], "answer": "B"},
                    ],
                    "self_test_phrase": "先建系再求法向量",
                }
            ],
            "knowledge_sections": {
                "第1天": [
                    {
                        "title": "线面角动作链",
                        "mixed": {
                            "blanks": [("先求____向量", "法")],
                            "choices": [{"question": "先做什么？", "options": ["A. 建系", "B. 猜"], "answer": "A"}],
                        },
                        "oral": {"prompts": ["为什么求法向量？"], "keypoints": ["把平面转成可计算对象"]},
                    }
                ]
            },
        }

        lesson, days, reminders = adapt_plan_to_review_template(plan_data)
        knowledge_sections = extract_knowledge_sections(plan_data)

        self.assertEqual(len(lesson["full_review_topics"]), 17)
        self.assertEqual(lesson["quotes"], [f"课堂原话{i}" for i in range(1, 13)])
        self.assertEqual(reminders, ["先标数据", "再求法向量"])
        self.assertEqual(len(days[0]["blanks"]), 7)
        self.assertEqual(len(days[0]["choices"]), 2)
        self.assertIn("第1天", knowledge_sections)
        self.assertEqual(knowledge_sections["第1天"][0]["title"], "线面角动作链")

    def test_adapt_plan_to_review_template_accepts_writer_style_plan(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        lesson, days, reminders = adapt_plan_to_review_template(writer_style_single_lesson_plan())

        self.assertEqual(lesson["title"], "分式方程入门复习计划")
        self.assertEqual(days[0]["focus"], "定义、步骤、检验。")
        self.assertEqual(days[0]["blanks"][0], ("分式方程去分母后化为______方程。", "整式"))
        self.assertEqual(days[0]["choices"][0]["question"], "下列哪一步最容易产生增根？")
        self.assertTrue(reminders)

    def test_adapt_plan_to_review_template_accepts_components_only_plan(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        lesson, days, reminders = adapt_plan_to_review_template(components_only_single_lesson_plan())

        self.assertEqual(lesson["title"], "不等式与函数复习复习计划")
        self.assertIn("不等式与函数复习", lesson["full_review_topics"])
        self.assertEqual(days[0]["blanks"][0], ("已知 x>0,y>0，且 1/x+2/y=1，则 x+2y 的最小值是______。", "9"))
        self.assertEqual(days[0]["choices"][0]["question"], "下列函数中，与 f(x)=(x²-1)/(x-1) 相等的是（ ）。")
        self.assertTrue(any("解函数不等式时，第一步先判断" in task for task in days[0]["tasks"]))
        self.assertTrue(reminders)

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

        with patch("app.has_review_plan_api_key", return_value=True), \
             patch("app.ensure_feature_credits_available"), \
             patch("app._start_review_plan_generation_thread") as start_thread:

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

        self.assertEqual(response.status_code, 202)
        lesson_id = response.get_json()["id"]
        start_thread.assert_called_once()

        with patch("app._run_ai_feature_with_charge", return_value=copy.deepcopy(DEMO_PLAN)), \
             patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf") as generate_pdf:
            generate_pdf.return_value = str(self.base / "api-review-plan.pdf")
            app_module._run_review_plan_generation_job(
                lesson_id=lesson_id,
                user={"id": 1, "organization_id": 1},
                chat_provider="deepseek",
                chat_model="deepseek-chat",
                request_key=start_thread.call_args.kwargs["request_key"],
                request_id=start_thread.call_args.kwargs["request_id"],
            )

        generate_pdf.assert_called_once()

    def test_cmd_add_uses_review_template_generator(self):
        import argparse

        with patch("review_plan_workflow.nodes.plan_generator.generate_review_plan_json", return_value=(valid_single_lesson_plan(subject="数学", topic="一次函数"), {})), \
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
