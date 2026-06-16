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
                ],
                "choices": [
                    {
                        "stem": "下列哪一步最容易产生增根？",
                        "options": ["A. 去分母", "B. 抄题", "C. 排版", "D. 口算"],
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
                ],
                "choices": [
                    {
                        "question": "将军饮马问题先做什么？",
                        "options": ["A. 作对称点", "B. 背答案", "C. 改颜色", "D. 删条件"],
                        "answer": "A",
                    }
                ],
                "completion_standard": "能复述课堂主线并完成当天自测。",
            }
            for day, date_part in ((1, 16), (2, 17), (7, 22), (14, 29), (30, 15))
        ],
    }
