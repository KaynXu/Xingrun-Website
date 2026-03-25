#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成演示复习计划 PDF（新版间隔复习：第1/2/7/14/30/60天）
"""
import json
from pathlib import Path
from pdf_engine import generate_lesson_pdf
from lesson_manager import save_lesson

DEMO_PLAN = {
    "lesson_info": {
        "subject": "数学",
        "grade": "初二",
        "topic": "一次函数",
        "key_categories": ["函数定义与图像", "斜率与截距", "待定系数法", "函数解析式求法", "图像特征判断", "综合应用"]
    },
    "weak_points_summary": "学生对斜率符号与图像方向易混淆，待定系数法解题步骤不规范。",
    "days": [
        {
            "day": 1,
            "label": "课后第1天复习",
            "time": "4–5分钟",
            "type": "day1",
            "steps": [
                {
                    "step_label": "⏱ 第1步（1分钟）",
                    "title": "口头回忆各大板块",
                    "items": [
                        {"type": "body", "text": "这节课主要学了哪几块内容？"},
                        {"type": "fill", "text": "① ____ ② ____ ③ ____ ④ ____"}
                    ]
                },
                {
                    "step_label": "⏱ 第2步（2分钟）",
                    "title": "翻笔记，看关键提醒",
                    "items": [
                        {"type": "fill", "text": "① 一次函数的一般形式：y = ____ x + ____（k≠0）"},
                        {"type": "fill", "text": "② k > 0 时图像从左下到____，k < 0 时从左上到____"},
                        {"type": "fill", "text": "③ 待定系数法：先设 y = kx + b，再代入____个已知点"}
                    ]
                },
                {
                    "step_label": "⏱ 第3步（1–2分钟）",
                    "title": "口头自测",
                    "items": [
                        {"type": "fill", "text": "Q1：y = 2x - 3 中，斜率是____，y轴截距是____"},
                        {"type": "fill", "text": "Q2：过(0,1)和(2,5)的一次函数解析式是____"},
                        {"type": "fill", "text": "Q3：k < 0, b > 0 的函数图像在哪几个象限？答：____"},
                        {"type": "fill", "text": "Q4：一次函数与正比例函数的区别是____"}
                    ]
                }
            ],
            "self_test_phrase": "出发口令：「一次函数 y=kx+b，k决定方向，b决定位置，两点定一线！」"
        },
        {
            "day": 2,
            "label": "课后第2天复习",
            "time": "3分钟",
            "theme": "函数定义与图像",
            "type": "daily",
            "items": [
                {"type": "body", "text": "📌 今天做题前先记这几条："},
                {"type": "fill", "text": "① 一次函数定义：自变量 x 的次数为____，且 k____0"},
                {"type": "fill", "text": "② 图像是一条____，不过原点的叫____函数"},
                {"type": "fill", "text": "③ 当 b = 0 时，一次函数变成____函数"}
            ],
            "self_test_phrase": "出发口令：「k≠0，b是截距，过两点画直线！」"
        },
        {
            "day": 7,
            "label": "课后第7天复习",
            "time": "3分钟",
            "theme": "斜率与截距",
            "type": "daily",
            "items": [
                {"type": "body", "text": "📌 距上课一周，回顾斜率判断："},
                {"type": "fill", "text": "① k > 0：图像从左____到右____（递增）"},
                {"type": "fill", "text": "② k < 0：图像从左____到右____（递减）"},
                {"type": "fill", "text": "③ |k| 越大，直线越____；b > 0 图像与 y 轴交于____侧"}
            ],
            "self_test_phrase": "出发口令：「k的符号定方向，b的符号定截距位置！」"
        },
        {
            "day": 14,
            "label": "课后第14天复习",
            "time": "3分钟",
            "theme": "待定系数法",
            "type": "daily",
            "items": [
                {"type": "body", "text": "📌 两周后，待定系数法步骤巩固："},
                {"type": "fill", "text": "① 第一步：设解析式为 y = ____x + ____"},
                {"type": "fill", "text": "② 第二步：将两个已知点分别代入方程，得到____元____次方程组"},
                {"type": "fill", "text": "③ 第三步：解方程组求出 k = ____，b = ____，写出解析式"}
            ],
            "self_test_phrase": "出发口令：「设、代、解、写——四步搞定待定系数法！」"
        },
        {
            "day": 30,
            "label": "课后第30天复习",
            "time": "3分钟",
            "theme": "函数解析式求法 + 图像特征判断",
            "type": "daily",
            "items": [
                {"type": "body", "text": "📌 一个月后，这些最容易忘："},
                {"type": "fill", "text": "① 已知图像过第一、三象限，则 k____0（填>/<）"},
                {"type": "fill", "text": "② 图像过(1,3)和(-1,-1)，解析式为 y = ____"},
                {"type": "fill", "text": "③ 两直线平行的条件：k₁____k₂，b₁____b₂"}
            ],
            "self_test_phrase": "出发口令：「象限判k的符号，两点求解析式，平行看k相等！」"
        },
        {
            "day": 60,
            "label": "课后第60天复习",
            "time": "4分钟",
            "theme": "一次函数综合回顾",
            "type": "daily",
            "items": [
                {"type": "body", "text": "📌 两个月后最终巩固，全面回顾一次函数："},
                {"type": "fill", "text": "① 一次函数 y=kx+b 的三要素：____、____、____"},
                {"type": "fill", "text": "② k>0, b<0：图像在____象限内无交点"},
                {"type": "fill", "text": "③ 一次函数与 x 轴的交点坐标：(____，0)"},
                {"type": "fill", "text": "④ 实际问题中，k 表示____，b 表示____（初始值）"}
            ],
            "self_test_phrase": "出发口令：「一次函数我全掌握——定义、图像、求法、应用，一个不漏！」"
        }
    ],
    "questions": [
        {"question": "一次函数 y=kx+b 中，k 的作用是什么？", "answer": "k 是斜率，决定函数图像的倾斜方向和程度", "category": "函数定义与图像", "day": 1},
        {"question": "b 在一次函数中代表什么？", "answer": "b 是 y 轴截距，图像与 y 轴交于 (0,b)", "category": "函数定义与图像", "day": 1},
        {"question": "k>0 时函数图像的走向如何？", "answer": "从左下到右上，y 随 x 增大而增大（递增）", "category": "斜率与截距", "day": 2},
        {"question": "k<0 时函数图像的走向如何？", "answer": "从左上到右下，y 随 x 增大而减小（递减）", "category": "斜率与截距", "day": 2},
        {"question": "待定系数法的步骤是什么？", "answer": "①设 y=kx+b ②代入两个已知点 ③列方程组求k、b ④写出解析式", "category": "待定系数法", "day": 7},
        {"question": "过点(0,2)和(3,8)的一次函数解析式是？", "answer": "y=2x+2", "category": "函数解析式求法", "day": 7},
        {"question": "一次函数和正比例函数有何区别？", "answer": "正比例函数是 b=0 的特殊一次函数，图像过原点", "category": "函数定义与图像", "day": 14},
        {"question": "y=-3x+1 的图像在哪些象限？", "answer": "第一、二、四象限（k<0, b>0）", "category": "图像特征判断", "day": 14},
        {"question": "两条一次函数图像平行的条件是？", "answer": "k₁=k₂ 且 b₁≠b₂（斜率相等，截距不等）", "category": "综合应用", "day": 30},
        {"question": "一次函数 y=2x-4 与 x 轴的交点是？", "answer": "令 y=0，得 x=2，交点为(2,0)", "category": "综合应用", "day": 30},
        {"question": "实际问题中，k 和 b 各表示什么含义？", "answer": "k 表示变化率（每单位变化量），b 表示初始值", "category": "综合应用", "day": 60},
        {"question": "已知 y=kx+b 图像过第二、四象限，k、b 的符号是？", "answer": "k<0（过二四象限），b=0，即为正比例函数；若过第二象限且截距为正则 k<0, b>0", "category": "图像特征判断", "day": 60}
    ],
    "weekly_review_prompts": [
        "这次复习哪个知识点最容易忘？",
        "哪天的复习最有效？原因是",
        "下次做题前要额外注意：",
        "我需要老师再讲一遍的是："
    ]
}

if __name__ == "__main__":
    out_path = "data/pdfs/demo_一次函数_间隔复习计划.pdf"
    Path("data/pdfs").mkdir(parents=True, exist_ok=True)
    
    # 生成 PDF
    result = generate_lesson_pdf(DEMO_PLAN, out_path)
    print(f"✅ PDF 已生成：{result}")
    
    # 保存到数据库
    lesson_id = save_lesson(
        date_str="2026-03-25",
        subject="数学",
        grade="初二",
        topic="一次函数",
        summary="本节课学习了一次函数的定义、图像特征、斜率与截距的含义、待定系数法求解析式，以及图像象限分析。",
        weak_points="斜率符号与图像方向易混淆，待定系数法解题步骤不规范。",
        plan=DEMO_PLAN,
        pdf_path=result,
        class_id=0,
    )
    print(f"✅ 课程已保存到数据库，ID = {lesson_id}")
    print(f"📌 在浏览器打开：http://127.0.0.1:5000/lessons/{lesson_id}")
