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

    def test_adapt_plan_preserves_custom_day_label(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan = valid_single_lesson_plan(subject="数学", topic="一次函数")
        plan["days"] = [plan["days"][0]]
        plan["days"][0]["day"] = 1
        plan["days"][0]["label"] = "考前当天冲刺"

        _lesson, days, _reminders = adapt_plan_to_review_template(plan)

        self.assertEqual(days[0]["day"], "考前当天冲刺")

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

        self.assertEqual(reminders[0], "当天课后复习要完整扫过课堂主线。")
        self.assertEqual(lesson["full_review_topics"], ["1. 折射率与全反射", "[ ] 干涉", "机械波->图像判断"])
        self.assertEqual(days[0]["focus"], "[已完成] 第1天复盘")
        self.assertEqual(days[0]["tasks"][0], "题型 [填空题·折射率]")
        self.assertEqual(days[0]["tasks"][1], "老师问：为什么进入高折射率介质后波长变短？")
        self.assertEqual(days[0]["tasks"][2], "提示：先抓频率不变")
        self.assertEqual(days[0]["blanks"][0], ("[ ] 折射率公式->____", "n=c/v"))
        self.assertEqual(days[0]["quotes"], ["注意：易错点：别把质点振动当成随波迁移"])

    def test_adapt_plan_to_review_template_hides_pending_confirmation_copy_for_one_day_plan(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template, build_single_lesson_pdf_filename

        plan = valid_single_lesson_plan(subject="数学", topic="代数基础巩固（高一衔接基础补漏，待确认）")
        plan["days"] = [plan["days"][0]]
        plan["days"][0]["day"] = 1
        plan["days"][0]["label"] = "当天复现"

        lesson, days, reminders = adapt_plan_to_review_template(plan)
        filename = build_single_lesson_pdf_filename(plan, suffix="96-v1")

        self.assertEqual(lesson["title"], "代数基础巩固复习计划")
        self.assertNotIn("待确认", lesson["title"])
        self.assertEqual(days[0]["day"], "当天课后复习")
        self.assertEqual(reminders[0], "当天课后复习要完整扫过课堂主线。")
        self.assertEqual(filename, "代数基础巩固-96-v1.pdf")

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
        self.assertEqual(lesson["quotes"], [f"课堂原话{i}" for i in range(1, 6)])
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

        self.assertEqual(lesson["title"], "不等式与函数复习计划")
        self.assertIn("不等式与函数复习", lesson["full_review_topics"])
        self.assertEqual(days[0]["blanks"][0], ("已知 x>0,y>0，且 1/x+2/y=1，则 x+2y 的最小值是______。", "9"))
        self.assertEqual(days[0]["choices"][0]["question"], "下列函数中，与 f(x)=(x²-1)/(x-1) 相等的是（ ）。")
        self.assertTrue(any("解函数不等式时，第一步先判断" in task for task in days[0]["tasks"]))
        self.assertFalse(any("下列函数中" in task for task in days[0]["tasks"]))
        self.assertTrue(reminders)

    def test_adapt_plan_to_review_template_keeps_question_stems_out_of_execution_checklist(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan = {
            "subject": "数学",
            "plan_title": "试卷评讲混合专题复盘复习计划",
            "lesson_info": {"topic": "", "key_categories": []},
            "full_review_topics": ["等式判断推导习惯", "审题列式语义转化", "无图几何分类讨论"],
            "days": [
                {
                    "day": 1,
                    "goal": "把整节课的知识框架重新搭起来。",
                    "focus": "框架搭建。",
                    "items": [
                        {"type": "body", "text": "选择题：下列说法正确的是（ ）"},
                        {"type": "body", "text": "选择题：关于“无图有偶”的说法，下列理解错误的是（ ）"},
                        {"type": "body", "text": "填空题正确率≥80%，能复述绝对值相等的两种可能。"},
                    ],
                    "blanks": [
                        {"text": "若 a²=b²，则 a 与 b 的关系是______。", "answer": "相等或互为相反数"},
                        {"text": "分式取倒数前必须先检查______。", "answer": "分母不为0"},
                    ],
                    "choices": [
                        {
                            "question": "下列说法正确的是（ ）",
                            "options": ["A. 直接取倒数", "B. 先看分母", "C. 忽略范围", "D. 只看答案"],
                            "answer": "B",
                        }
                    ],
                }
            ],
        }

        lesson, days, _reminders = adapt_plan_to_review_template(plan)

        self.assertEqual(lesson["title"], "试卷评讲混合专题复盘复习计划")
        self.assertTrue(any("完成选择题" in task for task in days[0]["tasks"]))
        self.assertFalse(any(task.startswith("选择题") for task in days[0]["tasks"]))
        self.assertFalse(any("下列说法正确的是" in task for task in days[0]["tasks"]))
        self.assertFalse(any("正确率≥80%" in task for task in days[0]["tasks"]))

    def test_build_single_lesson_pdf_filename_prefers_short_plan_title(self):
        from review_plan_templates.single_lesson_pdf import build_single_lesson_pdf_filename

        plan = {
            "subject": "数学",
            "plan_title": "试卷评讲混合专题复盘复习计划",
            "lesson_info": {"topic": "", "key_categories": []},
            "full_review_topics": [
                "等式判断推导习惯-由若到则逐步检查，取倒数需分母",
                "平方相等与绝对值相等的结论边界",
                "审题列式语义转化-应用题中翻译理想购买数量",
            ],
            "days": [{"day": 1, "goal": "复盘试卷评讲。", "blanks": [{"text": "a²=b² 推出 a______b。", "answer": "=或=-"}]}],
        }

        filename = build_single_lesson_pdf_filename(plan, suffix="80-v1")

        self.assertEqual(filename, "试卷评讲混合专题复盘-80-v1.pdf")
        self.assertNotIn("等式判断推导习惯", filename)

    def test_adapt_plan_to_review_template_promotes_active_recall_into_printable_day_content(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan = {
            "lesson_info": {
                "topic": "不等式与函数复习",
                "key_categories": ["全方和不等式", "抽象函数定义域", "同一函数辨析"],
            },
            "days": [
                {
                    "day": 1,
                    "label": "第1天",
                    "blanks": [
                        {
                            "text": "全方和不等式：若 $x,y>0$，则 $\\frac{a^2}{x}+\\frac{b^2}{y}\\ge_______$。",
                            "answer": "$\\frac{(a+b)^2}{x+y}$",
                        }
                    ],
                    "choices": [
                        {
                            "question": "抽象函数定义域先看什么？",
                            "options": ["A. 括号整体", "B. 字体", "C. 页码", "D. 颜色"],
                            "answer": "A",
                        }
                    ],
                    "active_recall": {
                        "type": "课堂方法回溯",
                        "items": [
                            {
                                "instruction": "完成抽象函数定义域桥梁法。",
                                "blanks": [
                                    {"label": "已知 $f(2x+3)$ 定义域 $[1,2]$，则 $2x+3$ 的范围是_______。", "answer": "$[5,7]$"},
                                    {"label": "因此令 $3x+6$ 满足_______。", "answer": "$5\\le3x+6\\le7$"},
                                ],
                            }
                        ],
                    },
                },
                {
                    "day": 2,
                    "label": "第2天",
                    "blanks": [{"text": "同一函数判断先比较_______。", "answer": "定义域"}],
                    "choices": [
                        {
                            "question": "下列哪组函数一定相同？",
                            "options": ["A. 解析式相同且定义域相同", "B. 只看解析式", "C. 只看图像颜色", "D. 只看题号"],
                            "answer": "A",
                        }
                    ],
                    "active_recall": {
                        "type": "老师追问口述卡片",
                        "items": [
                            {
                                "question": "题干：$f(x)=\\lg(x-1)$。问：为什么解 $f(x+2)>f(3x-4)$ 不能只比较括号大小？",
                                "answer_ref": "两个括号都必须先进入 $f$ 的定义域。",
                            }
                        ],
                    },
                },
            ],
        }

        _lesson, days, _reminders = adapt_plan_to_review_template(plan)

        self.assertEqual(len(days[0]["blanks"]), 1)
        self.assertTrue(any("桥梁法" in card for card in days[0]["method_cards"]))
        self.assertTrue(any("不能只比较括号大小" in card for card in days[1]["method_cards"]))
        self.assertTrue(any("课堂方法复盘卡片" in task for task in days[0]["tasks"]))

    def test_adapt_plan_to_review_template_keeps_all_explicit_choices(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan = {
            "lesson_info": {
                "subject": "数学",
                "topic": "勾股数与特殊角",
                "key_categories": ["勾股定理", "整数勾股数", "特殊直角三角形"],
            },
            "full_review_topics": ["勾股定理", "整数勾股数", "特殊直角三角形"],
            "days": [
                {
                    "day": 1,
                    "blanks": [
                        {"text": f"第{i}题：直角三角形满足______。", "answer": "$a^2+b^2=c^2$"}
                        for i in range(1, 6)
                    ],
                    "choices": [
                        {
                            "question": f"选择题{i}：下列哪组是勾股数？",
                            "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                            "answer": "A",
                        }
                        for i in range(1, 4)
                    ],
                }
            ],
        }

        _lesson, days, _reminders = adapt_plan_to_review_template(plan)

        self.assertEqual(len(days[0]["choices"]), 3)
        self.assertEqual(days[0]["choices"][2]["question"], "选择题3：下列哪组是勾股数？")

    def test_adapt_plan_to_review_template_keeps_all_printable_questions(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template
        from review_plan_workflow.printable_questions import count_printable_questions

        plan = {
            "lesson_info": {
                "subject": "数学",
                "topic": "勾股数与特殊角",
                "key_categories": ["勾股定理", "整数勾股数", "特殊直角三角形"],
            },
            "full_review_topics": ["勾股定理", "整数勾股数", "特殊直角三角形"],
            "days": [
                {
                    "day": 1,
                    "blanks": [
                        {"text": f"第{i}题：勾股定理等式为______。", "answer": "$a^2+b^2=c^2$"}
                        for i in range(1, 9)
                    ],
                    "choices": [
                        {
                            "question": f"选择题{i}：下列哪组是勾股数？",
                            "options": ["A. 3,4,5", "B. 2,2,5", "C. 1,1,3", "D. 4,4,9"],
                            "answer": "A",
                        }
                        for i in range(1, 3)
                    ],
                }
            ],
        }

        _lesson, days, _reminders = adapt_plan_to_review_template(plan)
        counts = count_printable_questions(plan)

        self.assertEqual(counts.total_visible_questions, 10)
        self.assertEqual(len(days[0]["blanks"]) + len(days[0]["choices"]), 10)

    def test_adapt_plan_to_review_template_formats_structured_active_recall_without_schema_keys(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan = {
            "lesson_info": {"topic": "瓜豆模型", "key_categories": ["瓜豆模型"]},
            "days": [
                {
                    "day": 1,
                    "focus": "模型回看",
                    "goal": "复述瓜豆模型",
                    "active_recall": {
                        "instructions": [
                            {
                                "intro": "请尝试复述课堂12题U绝对值操作的分类讨论方法。",
                                "steps": [
                                    "步骤1：因为有绝对值，全正和全负的符号组合化简结果____。",
                                    "步骤2：除去全正、全负后，还有____种不同的符号组合。",
                                ],
                                "answers": ["相同", "6"],
                            }
                        ],
                        "cards": [
                            {
                                "stem": "在triangle ABC中，angle BAC=90^circ，先说明旋转中心。",
                                "answer_ref": "课堂笔记第12题",
                            }
                        ],
                    },
                }
            ],
        }

        _lesson, days, _reminders = adapt_plan_to_review_template(plan)
        method_text = "\n".join(days[0]["method_cards"])

        self.assertIn("请尝试复述课堂12题U绝对值操作的分类讨论方法。", method_text)
        self.assertIn("步骤1：因为有绝对值", method_text)
        self.assertIn("步骤2：除去全正、全负后", method_text)
        self.assertIn("在△ABC中，∠BAC=90°", method_text)
        self.assertNotIn("{", method_text)
        self.assertNotIn("'intro'", method_text)
        self.assertNotIn("'steps'", method_text)
        self.assertNotIn("'answers'", method_text)

    def test_adapt_plan_to_review_template_preserves_latex_for_pdf_formula_rendering(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan = valid_single_lesson_plan(subject="数学", topic="全方和不等式")
        formula = r"$\frac{a^2}{x}+\frac{b^2}{y}\ge \frac{(a+b)^2}{x+y}$"
        plan["days"][0]["steps"][1]["items"][0]["text"] = f"全方和不等式：{formula}"

        _lesson, days, _reminders = adapt_plan_to_review_template(plan)

        self.assertIn(r"\frac{a^2}{x}", days[0]["blanks"][1][0])
        self.assertNotIn("(a²)/(x)", days[0]["blanks"][1][0])

    def test_adapt_plan_to_review_template_does_not_fabricate_multiple_choice_options(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan = valid_single_lesson_plan(subject="数学", topic="全方和不等式")
        for day in plan["days"]:
            day["choices"] = []
        plan["questions"] = [
            {
                "question": r"写出全方和不等式：$\frac{a^2}{x}+\frac{b^2}{y}\ge ?$",
                "answer": r"$\frac{(a+b)^2}{x+y}$",
            }
        ]

        _lesson, days, _reminders = adapt_plan_to_review_template(plan)

        self.assertEqual(days[0]["choices"], [])

    def test_adapt_plan_to_review_template_accepts_global_questions_only_with_real_options(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template

        plan = valid_single_lesson_plan(subject="数学", topic="全方和不等式")
        for day in plan["days"]:
            day["choices"] = []
        plan["questions"] = [
            {
                "question": "下列哪一个是全方和不等式的标准形式？",
                "options": [
                    r"A. $\frac{a^2}{x}+\frac{b^2}{y}\ge \frac{(a+b)^2}{x+y}$",
                    r"B. $\frac{a+b}{x+y}\ge a^2+b^2$",
                    "C. a²+b²≥2ab",
                    "D. x+y≥a+b",
                ],
                "answer": "A",
            }
        ]

        _lesson, days, _reminders = adapt_plan_to_review_template(plan)

        self.assertEqual(days[0]["choices"][0]["question"], "下列哪一个是全方和不等式的标准形式？")
        self.assertIn(r"\frac{a^2}{x}", days[0]["choices"][0]["options"][0])

    def test_generate_single_lesson_pdf_escapes_math_comparison_symbols(self):
        from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf

        plan = components_only_single_lesson_plan()
        day_one_components = plan["days"][0]["components"]
        blanks_card = next(item for item in day_one_components if item["type"] == "blanks_card")
        choices_card = next(item for item in day_one_components if item["type"] == "choices_card")
        blanks_card["items"][0]["stem"] = "已知 x>0，y>0，且 x+y=1，则 1/x+9/y 的最小值为 ______。"
        choices_card["items"][0]["stem"] = "已知 f(x) 是定义在 R 上的增函数，则不等式 f(1-x²)<f(2x) 的解集是（ ）"
        choices_card["items"][0]["options"] = [
            "A. -1<x<2",
            "B. x>2",
            "C. x<1",
            "D. 无解",
        ]
        output_path = self.base / "comparison-symbols.pdf"

        result = generate_single_lesson_pdf(plan, output_path)

        self.assertEqual(Path(result), output_path.resolve())
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)

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

    def test_collect_plan_quotes_keeps_homepage_quotes_concise(self):
        from review_plan_templates.single_lesson_pdf import collect_plan_quotes

        plan = {
            "quotes": ["定义域永远指 x。"],
            "lesson_info": {"quotes": ["看见 f 一坨优先第一。"]},
            "days": [
                {
                    "quotes": ["脱衣服时，定语别脱丢。"],
                    "self_test_phrase": "能独立完成换元和方程组两种解析式求法。",
                    "items": [
                        {"type": "body", "text": "快速回顾课堂核心，建立定义域和解析式求法的基本框架。"}
                    ],
                }
            ],
        }

        quotes = collect_plan_quotes(plan)

        self.assertEqual(quotes, ["定义域永远指 x。", "看见 f 一坨优先第一。", "脱衣服时，定语别脱丢。"])
        self.assertNotIn("能独立完成换元和方程组两种解析式求法。", quotes)

    def test_collect_plan_quotes_filters_instruction_fallback_text(self):
        from review_plan_templates.single_lesson_pdf import adapt_plan_to_review_template, collect_plan_quotes

        plan = {
            "lesson_info": {"topic": "不等式与函数复习", "key_categories": ["定义域限制", "函数不等式"]},
            "quotes": ["每一个复习日都要完整复习整节课内容。"],
            "days": [
                {
                    "day": 1,
                    "label": "第1天",
                    "goal": "复现定义域限制。",
                    "focus": "定义域。",
                    "blanks": [{"text": "函数不等式先判断______。", "answer": "定义域"}],
                    "choices": [
                        {
                            "question": "解函数不等式最先检查什么？",
                            "options": ["A. 定义域", "B. 字号", "C. 页码", "D. 颜色"],
                            "answer": "A",
                        }
                    ],
                    "self_test_phrase": "请完成以上填空和选择题，并对照答案自检。",
                }
            ],
        }

        self.assertEqual(collect_plan_quotes(plan), [])
        lesson, days, _reminders = adapt_plan_to_review_template(plan)
        self.assertEqual(lesson["quotes"], [])
        self.assertEqual(days[0]["quotes"], [])

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
