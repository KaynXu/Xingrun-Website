from __future__ import annotations

import copy

from demo_plan import DEMO_PLAN


def valid_single_lesson_plan(*, subject: str = "数学", topic: str = "一次函数") -> dict:
    plan = copy.deepcopy(DEMO_PLAN)
    plan["lesson_info"]["subject"] = subject
    plan["lesson_info"]["topic"] = topic
    plan["days"] = [day for day in plan.get("days", []) if day.get("day") in {1, 2, 7, 14, 30}]
    if subject in {"物理", "physics"}:
        plan["weak_points_summary"] = "学生需要巩固公式、单位、实验、图像和适用条件。"
        plan.setdefault("knowledge_sections", {})["physics_safety"] = {
            "formula": "先写公式，再核对单位和适用条件。",
            "experiment": "实验题要说明变量控制和图像含义。",
        }
    elif subject in {"雅思", "ielts"}:
        plan["weak_points_summary"] = "学生需要巩固 IELTS Reading 题型、同义替换和定位流程。"
    else:
        plan["weak_points_summary"] = "学生需要巩固题型入口、解题步骤、公式和错因复盘。"
    return plan


def writer_style_single_lesson_plan() -> dict:
    return {
        "lesson_info": {
            "date": "2026-06-14",
            "topic": "分式方程入门",
            "grade": "九年级",
            "weak_points": ["基础计算", "步骤表达"],
            "key_categories": ["分式方程定义", "去分母转化", "增根检验", "四步解法"],
        },
        "days": [
            {
                "day": day,
                "date": f"2026-06-{date_part:02d}",
                "time_minutes": 30,
                "title": f"第{day}天复习",
                "goal": "回顾分式方程的定义、去分母和增根检验。",
                "focus": "定义、步骤、检验。",
                "blanks": [
                    {"text": "分式方程去分母后化为______方程。", "answer": "整式"},
                    {"text": "解完后必须进行______。", "answer": "检验"},
                    {"text": "去分母前必须先确定最简公分母，并标出可能使分母为 0 的______。", "answer": "限制值"},
                ],
                "choices": [
                    {
                        "stem": "下列哪一步最容易产生增根？",
                        "options": ["A. 去分母", "B. 抄题", "C. 排版", "D. 口算"],
                        "answer": "A",
                    },
                    {
                        "stem": "解分式方程后为什么要代回原分母检验？",
                        "options": ["A. 排除增根", "B. 增加步骤字数", "C. 改变题意", "D. 跳过答案"],
                        "answer": "A",
                    }
                ],
                "active_recall": {
                    "instructions": "口述解分式方程的完整四步链条。",
                    "expected": "去分母、解整式、检验、写最终答案。",
                },
                "completion_standard": "能完整复述四步解法并说明为什么要检验。",
            }
            for day, date_part in ((1, 15), (2, 16), (7, 21), (14, 28), (30, 14))
        ],
    }


def desktop_writer_single_lesson_plan() -> dict:
    return {
        "subject": "math",
        "lesson_date": "2026-06-15",
        "generate_date": "2026-06-15",
        "topic": "二次函数最值与将军饮马综合复习",
        "grade": 9,
        "homepage": {
            "home_usage_box": "本复习计划基于课堂内容，用于课后间隔复习，建议每天用时20分钟。",
            "full_coverage_box": {
                "topics": ["二次函数最值", "将军饮马最短路径"],
                "methods": ["上减下/右减左", "设参数表达坐标", "轴对称转化", "顶点公式求最值"],
            },
            "golden_quote_box": "最值不在端点，就在对称轴。",
            "core_formula_card": {
                "formulas": [
                    "二次函数顶点横坐标：x = -b/(2a)",
                    "竖直线段长度（上减下）：|y上 - y下|",
                ]
            },
        },
        "days": [
            {
                "day_number": day,
                "date": f"2026-06-{date_part:02d}",
                "time_estimate": "20分钟",
                "title": f"第{day}天复习",
                "goal": "回顾课堂核心概念，复现关键方法。",
                "focus": "上减下/右减左、设参数、顶点公式、将军饮马。",
                "blanks": [
                    {"text": "竖直线段长度通常用______。", "answer": "上减下"},
                    {"text": "二次函数顶点横坐标公式是______。", "answer": "-b/(2a)"},
                    {"text": "将军饮马问题通常先作______点，再转化为直线最短。", "answer": "对称"},
                ],
                "choices": [
                    {
                        "question": "将军饮马问题先做什么？",
                        "options": ["A. 作对称点", "B. 背答案", "C. 改颜色", "D. 删条件"],
                        "answer": "A",
                    },
                    {
                        "question": "用顶点公式求最值前，必须先确认什么？",
                        "options": ["A. 自变量取值范围", "B. 字体大小", "C. 页码", "D. 题号颜色"],
                        "answer": "A",
                    }
                ],
                "completion_standard": "能复述课堂主线并完成当天自测。",
            }
            for day, date_part in ((1, 16), (2, 17), (7, 22), (14, 29), (30, 15))
        ],
    }


def components_only_single_lesson_plan() -> dict:
    return {
        "subject": "数学",
        "grade": "高一",
        "lesson_topic": "不等式与函数复习",
        "date_generated": "2026-06-16",
        "full_review_topics": [
            "不等式与函数复习",
            "全方和不等式",
            "柯西不等式",
            "函数定义域限制",
            "同一函数辨析",
            "函数不等式同解转化",
            "分段函数分类讨论",
        ],
        "home_usage_box": {
            "title": "课后复习计划使用说明",
            "content": "每次复习包含填空、选择、口述卡片三个板块。",
        },
        "days": [
            {
                "day_number": 1,
                "date": "2026年6月17日",
                "label": "第1天复习",
                "day_task_card": {
                    "review_goal": "复现不等式方法和函数定义域核心概念。",
                    "focus": "全方和、柯西、定义域。",
                },
                "components": [
                    {
                        "type": "golden_quote_box",
                        "quote": "全方和不等式要把分母加起来。",
                    },
                    {
                        "type": "blanks_card",
                        "title": "基础填空",
                        "items": [
                            {
                                "stem": "已知 x>0,y>0，且 1/x+2/y=1，则 x+2y 的最小值是______。",
                                "answer": "9",
                            },
                            {
                                "stem": "若 f(2x+1) 的定义域为 [1,2]，则 f(x) 的定义域为______。",
                                "answer": "[3,5]",
                            },
                        ],
                    },
                    {
                        "type": "choices_card",
                        "title": "概念辨析",
                        "items": [
                            {
                                "stem": "下列函数中，与 f(x)=(x²-1)/(x-1) 相等的是（ ）。",
                                "options": ["A. g(x)=x+1", "B. h(x)=x+1 (x≠1)", "C. k(x)=|x+1|", "D. p(x)=x"],
                                "answer": "B",
                            }
                        ],
                    },
                    {
                        "type": "active_recall_card",
                        "title": "课堂方法回溯",
                        "items": [
                            {
                                "stem": "解函数不等式时，第一步先判断______，第二步再检查______。",
                                "answer": "单调性, 定义域",
                            }
                        ],
                    },
                ],
                "blanks": [],
                "items": [],
                "choices": [],
                "self_test_phrase": "请完成以上填空和选择题，并对照答案自检。",
                "completion_criteria": "填空题全部正确，选择题能说出错因。",
            },
            *[
                {
                    "day_number": day,
                    "date": date_text,
                    "label": f"第{day}天复习",
                    "day_task_card": {
                        "review_goal": "复习不等式与函数定义域。",
                        "focus": "公式、定义域、解析式。",
                    },
                    "components": [
                        {
                            "type": "blanks_card",
                            "title": "基础填空",
                            "items": [
                                {
                                    "stem": f"第{day}天：函数相等必须同时满足解析式相同和______相同。",
                                    "answer": "定义域",
                                },
                                {
                                    "stem": f"第{day}天：柯西不等式常用于处理带系数的______关系。",
                                    "answer": "线性组合",
                                },
                                {
                                    "stem": f"第{day}天：判断两个函数是否相同，必须同时比较解析式和______。",
                                    "answer": "定义域",
                                },
                            ],
                        },
                        {
                            "type": "choices_card",
                            "title": "概念辨析",
                            "items": [
                                {
                                    "stem": f"第{day}天：求 f(2x-1) 的定义域时，最先检查什么？",
                                    "options": ["A. 复合内层范围", "B. 字体大小", "C. 作业题号", "D. 只看答案"],
                                    "answer": "A",
                                },
                                {
                                    "stem": f"第{day}天：下列哪一步最能避免函数不等式漏解？",
                                    "options": ["A. 先列定义域限制", "B. 直接去掉 f", "C. 只看答案", "D. 忽略真数限制"],
                                    "answer": "A",
                                }
                            ],
                        },
                        {
                            "type": "active_recall_card",
                            "title": "老师追问口述卡片",
                            "items": [
                                {
                                    "stem": f"题干：已知 f(x) 定义域为 [1,3]。问：求 f(2x-1) 定义域时为什么要令 2x-1 落在原定义域内？",
                                    "answer": "复合函数的内层必须进入外层函数定义域。",
                                }
                            ],
                        },
                    ],
                    "blanks": [],
                    "items": [],
                    "choices": [],
                    "self_test_phrase": "请完成以上填空和选择题，并对照答案自检。",
                }
                for day, date_text in ((2, "2026年6月18日"), (7, "2026年6月23日"), (14, "2026年6月30日"), (30, "2026年7月16日"))
            ],
        ],
    }
