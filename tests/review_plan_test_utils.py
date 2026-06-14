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
