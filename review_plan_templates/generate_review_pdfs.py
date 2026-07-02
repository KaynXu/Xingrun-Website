from __future__ import annotations

import json
import shutil
import subprocess
import sys
import re
import importlib.util
import platform
import warnings
from io import BytesIO
from functools import lru_cache
from typing import Any
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.graphics.shapes import Drawing, Group, Rect
from reportlab.graphics.svgpath import SvgPath
from reportlab.platypus import CondPageBreak, Flowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
OUTPUT_DIR = ROOT / "pdf_output"
OUTPUT_NAME = "review-plan-bilingual-quotes-10-15-quote-replay-layout.pdf"
FORMULA_DPI = 240
FORMULA_DEFAULT_FONT_SIZE = 10.3
FORMULA_DEFAULT_COLOR = "#5A4034"
MATHJAX_RENDERER_SCRIPT = REPO_ROOT / "frontend" / "scripts" / "render_mathjax_svg.mjs"


LESSON = {
    "title": "解三角形、数列与概率统计综合复习计划",
    "subtitle": "Spaced Review Plan for Trigonometry, Sequences, Probability, Solid Geometry, and Parabola",
    "audience": "老师发给学生使用 / For Teacher Distribution",
    "duration": "每次 10-20 分钟 / 10-20 minutes each time",
    "core_points": [
        "解三角形题要重点掌握余弦定理、正弦定理和化边化角。",
        "对边对角的多解问题要会借助正弦图像判断解的个数。",
        "数列高频考点包括递推公式、求和和最大项判断。",
        "概率统计常见结构是分布列、期望、二项分布与超几何分布。",
        "立体几何可优先建系找点，用坐标法求距离和面积。",
        "抛物线题要会求解析式，也要会做线段关系转化来简化第二问。",
    ],
    "full_review_topics": [
        "解三角形中的余弦定理与正弦定理 / Cosine law and sine law in triangles",
        "解三角形中的化边化角与恒等变换 / Transforming sides and angles with identities",
        "对边对角多解问题 / Ambiguous SSA cases and multiple solutions",
        "数列递推、求和与最大项 / Sequence recurrence, summation, and maximal term",
        "概率统计中的线性回归、卡方与独立性检验 / Regression, chi-square, and independence testing",
        "分布列、期望、二项分布、超几何分布 / Distribution tables, expectation, binomial and hypergeometric models",
        "概率最大项与数列最大项的类比 / Maximum probability term versus sequence maximum term",
        "立体几何中的建系找点 / Coordinate setup for solid geometry",
        "立体几何中的垂直平行、距离与面积 / Parallelism, perpendicularity, distance and area",
        "抛物线解析式与第二问化简技巧 / Parabola equation solving and second-question simplification",
    ],
    "quotes": [
        "解三角形的多解问题，当遇到对边对角时，可以用画正弦图像的方法。",
        "将样本的频率视为概率，此时概率就确定固定了。",
        "18题第一问必须做对，第二问做到指定步骤得5-6分就行了。",
        "立体几何建系找点，是最不用动脑的找法。",
        "求数列最大项，可以和前一项后一项去比较。",
        "计算题逻辑不难，最怕的是不仔细。",
    ],
}


FINAL_REMINDER_LINES = [
    "先几何、后代数；先翻译条件、后计算。 / Geometry first, algebra if needed.",
    "看到数量积，先想投影、几何恒等式和数形结合。 / Link dot product to projection and geometry.",
    "看到圆，判断标准式和三角换元哪个更顺。 / Choose between standard circle form and trig substitution.",
    "看到系数和与线性组合，优先回想等和线。 / Use equal-sum lines for coefficient sums.",
    "每个复习日都要扫完整节课。 / Review the full lesson every time.",
]


DAYS = [
    {
        "offset": 1,
        "day": "第1天 / Day 1",
        "focus": "第一次整课回放，先把各大题型的核心方法重新挂上钩。 / First replay focused on reconnecting each topic to its core method.",
        "goal": "能说出这节课涉及的主要模块，以及每个模块最先想到的方法。 / Name the main modules and the first method to try in each.",
        "tasks": [
            "先默写整节课的知识模块，再核对。Write down the lesson modules before checking notes.",
            "完成填空题，覆盖解三角形、数列、概率统计、立体几何和抛物线。Complete the blanks across all main topics.",
            "完成选择题，检查基础记忆与方法对应。Finish the multiple-choice items to test recall and method matching.",
            "读一次上课金句回顾，再口头复述整课主线。Read the class quotes once, then retell the lesson flow.",
        ],
        "blanks": [
            ("解三角形题中最核心的两个定理是____________定理和____________定理。", "余弦；正弦"),
            ("如果题目需要化边化角或角化边，常可借助____________定理。", "正弦"),
            ("对边对角的多解问题，常借助____________图像判断解的个数。", "正弦"),
            ("数列常考三个方向：递推公式、____________和____________。", "求和；最大项"),
            ("概率统计前三问若出现，通常难度不会太____________。", "大"),
            ("立体几何中较稳妥的找点方法是先____________。", "建系"),
            ("抛物线第一问高频目标是求____________。", "解析式"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合本节课对解三角形的强调 / Which best matches the lesson's emphasis in triangle solving?",
                "options": [
                    "A. 只背一个公式 / Memorize only one formula",
                    "B. 余弦定理和正弦定理通常要配合使用 / Cosine law and sine law usually work together",
                    "C. 解三角形只考面积 / Triangle solving only tests area",
                    "D. 完全不需要恒等变换 / Identities are never needed",
                ],
                "answer": "B",
            },
            {
                "question": "立体几何中老师更推荐的起手方式是 / The preferred starting method in solid geometry is:",
                "options": [
                    "A. 先猜结论 / Guess the conclusion first",
                    "B. 先建系找点 / Set coordinates and locate points first",
                    "C. 只画辅助线 / Draw auxiliary lines only",
                    "D. 只做几何证明 / Use pure proof only",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][0], LESSON["quotes"][3]],
    },
    {
        "offset": 2,
        "day": "第2天 / Day 2",
        "focus": "第二次整课复习，重点区分易混方法和题型入口。 / Second full review focused on distinguishing easy-to-confuse methods and entry points.",
        "goal": "能快速判断一道题是该先定理、先图像、先建系还是先列分布。 / Quickly decide whether to start with a theorem, graph, coordinates, or a probability model.",
        "tasks": [
            "快速过一遍全课覆盖清单。Run through the full coverage list once.",
            "完成填空题，重点复盘多解问题、数列最大项和概率题结构。Complete the blanks with focus on ambiguous cases, sequence maxima, and probability structure.",
            "完成选择题，纠正常见误判。Finish the choices to correct common misjudgments.",
            "口头说明为什么概率最大项和数列最大项有相通逻辑。Explain why maximum probability terms resemble maximum sequence terms.",
        ],
        "blanks": [
            ("对边对角多解问题中，可用 sin a 去表示____________。", "小a"),
            ("求数列最大项时，常通过和____________项、____________项比较来判断。", "前一；后一"),
            ("概率题第二问常见任务是求____________和____________。", "期望；分布列"),
            ("第三问若继续追问概率模型，常会写出____________分布或____________分布。", "二项；超几何"),
            ("概率最大项问题，其核心逻辑与____________最大项类似。", "数列"),
            ("若立体几何出在16、17题，第一问往往先考____________与____________。", "垂直；平行"),
            ("导数若出现在前面位置，通常难度会比较____________。", "简单"),
        ],
        "choices": [
            {
                "question": "下列哪一项最符合概率统计前三问的典型分工 / Which best matches the usual structure of the first three probability-statistics subquestions?",
                "options": [
                    "A. 先导数再立几再抛物线 / Derivatives, then solid geometry, then parabola",
                    "B. 先检验类问题，再期望分布列，再写二项或超几何模型 / Testing first, then expectation/distribution, then binomial or hypergeometric forms",
                    "C. 先数列求和，再三角变换 / Sequence sum, then trig transforms",
                    "D. 只考口算 / Mental arithmetic only",
                ],
                "answer": "B",
            },
            {
                "question": "哪一项最可能用于判断多解问题的解的个数 / Which is most likely used to judge the number of solutions in an ambiguous triangle case?",
                "options": [
                    "A. 正弦图像 / Sine graph",
                    "B. 抛物线对称轴 / Parabola axis",
                    "C. 立体坐标系 / 3D coordinate system",
                    "D. 二项分布表 / Binomial table",
                ],
                "answer": "A",
            },
        ],
        "quotes": [LESSON["quotes"][4]],
    },
    {
        "offset": 7,
        "day": "第7天 / Day 7",
        "focus": "一周后迁移，要求把不同题型背后的判断入口说清楚。 / One-week transfer review focused on clear entry signals for each problem type.",
        "goal": "不用落笔也能讲清：看到什么条件时该想到什么方法。 / Explain orally which condition signals which method.",
        "tasks": [
            "先口头复述全课方法地图。Orally restate the lesson's method map.",
            "回答老师提问卡片，每题都要补一句“为什么先这样做”。Answer oral prompts and add why that method comes first.",
            "再复盘一遍概率、立几、抛物线三类题的入口。Review the entry points for probability, solid geometry, and parabola.",
            "最后复述至少 3 句课堂原话。Retell at least 3 classroom quotes at the end.",
        ],
        "blanks": [
            ("看到解三角形中的边角混合关系，常先想到____________定理和____________定理。", "余弦；正弦"),
            ("看到“对边对角”且问解的个数时，常先画____________图像。", "正弦"),
            ("看到“最大项”时，不只是数列，____________题也可能这样处理。", "概率"),
            ("立体几何里“XYZ找距离”本质上是____________法。", "建系坐标"),
            ("抛物线第二问若线段关系复杂，可通过____________来简化。", "合理转化"),
            ("18题如果要保分，老师强调第一问必须____________。", "做对"),
            ("计算题失分常见原因不是逻辑太难，而是____________。", "计算不细"),
        ],
        "choices": [
            {
                "question": "哪一项最符合抛物线第二问的课堂思路 / Which best matches the class strategy for the second parabola subquestion?",
                "options": [
                    "A. 一律暴力展开 / Always expand everything brutally",
                    "B. 先做线段关系转化，再简化计算 / Transform line-segment relations first, then simplify",
                    "C. 不用图形 / Ignore geometry entirely",
                    "D. 只背答案 / Memorize the final answer only",
                ],
                "answer": "B",
            },
            {
                "question": "哪一项最符合本节课对得分策略的提醒 / Which best matches the lesson's score strategy?",
                "options": [
                    "A. 所有大题都要全做完 / Every long problem must be fully solved",
                    "B. 18题第一问必须做对，第二问做到指定步骤也有分 / Q18 part 1 must be correct, and specified steps in part 2 still earn points",
                    "C. 只做选择题 / Only do the multiple-choice section",
                    "D. 放弃计算题 / Give up calculation-heavy problems",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][2]],
    },
    {
        "offset": 14,
        "day": "第14天 / Day 14",
        "focus": "两周后校准，重点检查方法之间的边界和得分思维。 / Two-week calibration focused on method boundaries and scoring strategy.",
        "goal": "看到变式题时，仍能准确选入口，并知道保分重点在哪里。 / Choose the right entry point even for variants and know where points are secured.",
        "tasks": [
            "先口头总结这节课最容易错的 5 个点。First summarize the 5 easiest mistakes orally.",
            "回答老师提问卡片，重点说清为什么不用别的方法。Answer oral prompts and explain why alternative methods are weaker.",
            "复盘解三角形、概率统计、抛物线三类题的共同点：都要先抓已知条件结构。Recall their shared principle: start from the structure of the given conditions.",
            "最后再说一遍“逻辑不难，计算要细”的提醒。Close by restating the warning about careful calculation.",
        ],
        "blanks": [
            ("解三角形中若题目涉及中点、平行、n 等分线，通常属于____________情形。", "特殊"),
            ("中点相关公式和积化和差，常和____________变换联系起来。", "恒等"),
            ("线性回归、卡方检测、独立性检验更可能出现在概率统计的第____________问。", "一"),
            ("立体几何第一问如果只是垂直平行，整体难度通常不会太____________。", "大"),
            ("导数若出现在前三个题，课堂判断是：大概率很____________，甚至可画图求解。", "简单"),
            ("估分时老师特别提醒：题目逻辑不难，主要问题出在____________。", "计算"),
        ],
        "choices": [
            {
                "question": "哪一项最符合这节课对计算失分的判断 / Which best matches the lesson's view on calculation errors?",
                "options": [
                    "A. 题太偏太怪 / The problems are too strange",
                    "B. 逻辑太深根本不会 / The logic is too deep to understand",
                    "C. 主要卡在不仔细和逐步计算不稳 / The main issue is lack of care and unstable step-by-step calculation",
                    "D. 公式完全不会背 / Formulas are not memorized at all",
                ],
                "answer": "C",
            },
            {
                "question": "下列哪项最符合本节课的方法观 / Which best matches the lesson's method view?",
                "options": [
                    "A. 看见题目立刻硬算 / Start brute-force calculation immediately",
                    "B. 先判断题型入口，再决定工具 / Identify the entry point first, then choose the tool",
                    "C. 所有题都统一坐标化 / Convert every problem to coordinates",
                    "D. 所有题都背模板 / Memorize a template for every problem",
                ],
                "answer": "B",
            },
        ],
        "quotes": [LESSON["quotes"][1], LESSON["quotes"][5]],
    },
    {
        "offset": 30,
        "day": "第30天 / Day 30",
        "focus": "一个月后的总复盘，要求脱离课堂语境也能稳定调用这些题型工具。 / One-month final review for stable independent recall across all these topics.",
        "goal": "形成长期记忆：看到新题时能先识别模块，再决定得分策略与方法。 / Reach long-term memory: identify the module first, then choose method and scoring strategy.",
        "tasks": [
            "先默写整节课的题型-方法对照表。Write the topic-to-method map from memory.",
            "完成总复盘填空和选择，检查长期记忆是否稳定。Complete the final blanks and choices to test retention.",
            "任选一个专题，口头说出“入口-方法-易错点-得分点”。Pick one topic and retell its entry, method, pitfalls, and scoring point.",
            "最后读一遍上课金句回顾。Finish by reviewing the class quotes once more.",
        ],
        "blanks": [
            ("解三角形最核心的两条定理是____________定理与____________定理。", "余弦；正弦"),
            ("对边对角的多解问题，最典型的判断工具是____________图像。", "正弦"),
            ("数列最大项的判断，一般通过与____________项和____________项比较。", "前一；后一"),
            ("概率统计中，分布列之后常继续求____________。", "期望"),
            ("概率最大项与____________最大项的逻辑相通。", "数列"),
            ("立体几何中较稳妥的求距离方法是先____________。", "建系找点"),
            ("抛物线第一问重在求____________，第二问重在做____________。", "解析式；转化简化"),
        ],
        "choices": [
            {
                "question": "一个月后的理想状态是 / What is the ideal state after one month?",
                "options": [
                    "A. 只记住老师原话 / Remember only the teacher's quotes",
                    "B. 看到新题能先判断所属模块，再选方法和得分策略 / Identify the module first, then choose method and score strategy",
                    "C. 只会做原题 / Only solve the original examples",
                    "D. 每题都从最复杂的方法开始 / Start every problem with the most complex method",
                ],
                "answer": "B",
            },
            {
                "question": "本节课长期复习最该留下的是什么 / What should remain most clearly after long-term review?",
                "options": [
                    "A. 零散答案 / Isolated answers",
                    "B. 题号顺序 / Question ordering",
                    "C. 题型入口、方法与保分点之间的对应关系 / The mapping among entry signals, methods, and scoring priorities",
                    "D. 所有计算细节 / Every calculation detail",
                ],
                "answer": "C",
            },
        ],
        "quotes": [LESSON["quotes"][5]],
    },
]


KNOWLEDGE_SECTIONS = {
    "第1天 / Day 1": [
        {
            "title": "解三角形 / Triangle Solving",
            "mixed": {
                "blanks": [
                    ("解三角形第一、二问中，余弦定理与____________定理常常会同时出现。", "正弦"),
                ],
                "choices": [
                    {
                        "question": "若题目需要“化边化角”，优先联想哪条定理 / Which theorem is best for turning sides into angles or angles into sides?",
                        "options": [
                            "A. 正弦定理 / Sine law",
                            "B. 导数 / Derivatives",
                            "C. 立体几何建系 / Solid-geometry coordinates",
                            "D. 二项分布 / Binomial distribution",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么余弦定理和正弦定理常常需要一起出现？",
                    "什么情况下你会优先想“化边化角”或“角化边”？",
                    "遇到中点、平行、n 等分线时，解三角形题会有什么变化？",
                ],
                "keypoints": [
                    "因为题目往往边角混合，两个定理需要配合使用。",
                    "当题目想把边角关系转到更容易运算的形式时。",
                    "会进入特殊结构判断，需要结合恒等变换和比例关系。",
                ],
            },
        },
        {
            "title": "数列 / Sequences",
            "mixed": {
                "blanks": [
                    ("求数列最大项时，一个高频做法是与前一项、____________比较。", "后一项"),
                ],
                "choices": [
                    {
                        "question": "数列最大项的典型判断方式是 / The typical way to find a sequence maximum term is:",
                        "options": [
                            "A. 只求首项 / Only compute the first term",
                            "B. 与相邻项比较 / Compare with adjacent terms",
                            "C. 只求和 / Only sum the sequence",
                            "D. 直接猜 / Guess directly",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "数列这一块这节课主要复习了哪三类任务？",
                    "为什么最大项问题要和相邻项比较？",
                    "数列最大项和概率最大项有什么相通之处？",
                ],
                "keypoints": [
                    "递推公式、求和、最大项。",
                    "因为最大项通常体现为比前一项大、比后一项也大。",
                    "本质上都在找函数值或项值由增转减的拐点。",
                ],
            },
        },
    ],
    "第2天 / Day 2": [
        {
            "title": "概率统计 / Probability and Statistics",
            "mixed": {
                "blanks": [
                    ("概率统计题中，第二问高频任务是求期望和____________。", "分布列"),
                ],
                "choices": [
                    {
                        "question": "若第三问让写概率模型，常见的是 / If the third subquestion asks for a probability model, it often involves:",
                        "options": [
                            "A. 二项分布或超几何分布 / Binomial or hypergeometric distribution",
                            "B. 余弦定理 / Cosine law",
                            "C. 抛物线焦点 / Parabola focus",
                            "D. 立体角 / Solid angles",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "概率统计前三问各自常见什么任务？",
                    "为什么老师说如果前三题考概率统计，难度通常不会太大？",
                    "“将样本频率视为概率”这句话在题目里有什么作用？",
                ],
                "keypoints": [
                    "第一问偏检验类，第二问偏期望与分布列，第三问偏模型表达。",
                    "因为前面位置通常不会堆叠过难的统计综合。",
                    "它帮助把频率问题转成稳定概率模型。",
                ],
            },
        },
        {
            "title": "概率最大项 / Maximum Probability Term",
            "mixed": {
                "blanks": [
                    ("概率最大项的逻辑和____________最大项相似。", "数列"),
                ],
                "choices": [
                    {
                        "question": "判断概率最大项时，最适合借鉴哪一类思路 / Which idea is most helpful for maximum probability terms?",
                        "options": [
                            "A. 数列最大项的相邻比较思路 / Adjacent-term comparison from sequence maxima",
                            "B. 立体坐标建系 / Solid geometry coordinates",
                            "C. 三角恒等变换 / Trigonometric identities",
                            "D. 抛物线定义 / Parabola definition",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么概率最大项和数列最大项是同一路逻辑？",
                    "如果题目让你找概率最大项，你会先看什么量？",
                    "这类题为什么很适合用“和前后比较”的思路？",
                ],
                "keypoints": [
                    "都在找由增到减的转折点。",
                    "先看相邻项之间的比值或大小规律。",
                    "因为最大值往往落在相邻关系变化的位置。",
                ],
            },
        },
    ],
    "第7天 / Day 7": [
        {
            "title": "立体几何 / Solid Geometry",
            "mixed": {
                "blanks": [
                    ("立体几何中“XYZ找距离”的核心是先____________。", "建系找点"),
                ],
                "choices": [
                    {
                        "question": "立体几何第一问更常见的内容是 / The most common first subquestion in solid geometry is:",
                        "options": [
                            "A. 垂直和平行 / Perpendicularity and parallelism",
                            "B. 超难定点问题 / Very difficult fixed-point problems",
                            "C. 复杂导数证明 / Complex derivative proofs",
                            "D. 线性回归 / Linear regression",
                        ],
                        "answer": "A",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么老师说建系找点是最不用动脑的找法？",
                    "立体几何第一问通常为什么不会太难？",
                    "什么情况下第三问才可能出现更定制化的问题？",
                ],
                "keypoints": [
                    "因为坐标法把空间关系转成可计算距离。",
                    "因为第一问多是平行、垂直、距离、面积这类标准任务。",
                    "更复杂的定点或定制问题通常放在更后面的小问。",
                ],
            },
        },
        {
            "title": "导数与简单判断 / Derivatives and Simple Cases",
            "mixed": {
                "blanks": [
                    ("导数如果出现在前面的位置，课堂判断是：大概率比较____________。", "简单"),
                ],
                "choices": [
                    {
                        "question": "若导数题意外出现在前三个题，课堂建议更偏向 / If a derivative question appears early, the class suggests it is more likely to be:",
                        "options": [
                            "A. 非常复杂 / Extremely complex",
                            "B. 可以借助画图快速处理 / Quickly handled with a graph",
                            "C. 一定要用高难技巧 / Requiring advanced tricks",
                            "D. 与函数无关 / Unrelated to functions",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么老师判断导数出在前三个位置的概率很低？",
                    "如果真出了，为什么说画图可能就够了？",
                    "这类判断反映了什么考试命题规律？",
                ],
                "keypoints": [
                    "因为前面位置通常不会堆积过深的分析难题。",
                    "因为若放在前面，多半是结构简单、图像明显的题。",
                    "命题通常会控制整体难度梯度。",
                ],
            },
        },
    ],
    "第14天 / Day 14": [
        {
            "title": "抛物线 / Parabola",
            "mixed": {
                "blanks": [
                    ("抛物线第一问通常通过 PF 长度表达式和已知条件来求____________。", "p值"),
                ],
                "choices": [
                    {
                        "question": "抛物线第二问更优的课堂思路是 / The preferred class strategy for the second parabola subquestion is:",
                        "options": [
                            "A. 一上来全展开 / Expand everything immediately",
                            "B. 先做线段关系转化，再化简 / Transform segment relations first, then simplify",
                            "C. 直接放弃 / Give up directly",
                            "D. 改做概率题 / Switch to probability",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "抛物线第一问为什么常能从 PF 入手？",
                    "第二问中的“转化”为什么能显著减轻计算量？",
                    "如果只求保分，抛物线题应该抓住哪一步？",
                ],
                "keypoints": [
                    "因为焦点到点的距离常直接联系参数 p。",
                    "因为复杂线段积可以转成更容易计算的和差关系。",
                    "第一问务必做对，第二问先拿稳步骤分。",
                ],
            },
        },
        {
            "title": "得分策略 / Scoring Strategy",
            "mixed": {
                "blanks": [
                    ("老师对18题的得分建议是：第一问必须____________，第二问做到指定步骤也能得分。", "做对"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合这节课的保分观 / Which best matches the lesson's score-preserving strategy?",
                        "options": [
                            "A. 所有题都要追求满分 / Chase full marks on every problem",
                            "B. 先抓住必须做对的小问，再稳拿步骤分 / Secure must-get parts first, then collect step marks steadily",
                            "C. 只做选择题 / Only do multiple-choice questions",
                            "D. 放弃所有大题 / Give up all long-form questions",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么“第一问必须做对”是关键得分点？",
                    "为什么第二问做到指定步骤也有意义？",
                    "如何理解“逻辑不难，计算要细”这句话的得分含义？",
                ],
                "keypoints": [
                    "因为第一问通常是后续展开的基础，也是稳定分值来源。",
                    "因为规范步骤本身能拿到过程分。",
                    "不是方法不会，而是执行不稳导致丢分。",
                ],
            },
        },
    ],
    "第30天 / Day 30": [
        {
            "title": "题型入口总复盘 / Entry-Point Synthesis",
            "mixed": {
                "blanks": [
                    ("看到“对边对角”先想____________图像；看到“XYZ找距离”先想____________。", "正弦；建系"),
                ],
                "choices": [
                    {
                        "question": "哪一项最能体现“方法迁移” / Which best shows method transfer?",
                        "options": [
                            "A. 只记住原题答案 / Only remember the original answer",
                            "B. 看到新题还能认出它属于哪一类题型入口 / Recognize a new problem's entry point and category",
                            "C. 只会照抄板书 / Only copy the board work",
                            "D. 只记住题号 / Only remember question numbers",
                        ],
                        "answer": "B",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "一个月后你最该保留下来的“题型入口”有哪些？",
                    "看到一道新题时，你的判断顺序应该是什么？",
                    "这节课哪三类题最体现“先认入口再做题”？",
                ],
                "keypoints": [
                    "解三角形的定理入口、概率题的模型入口、立几的建系入口、抛物线的关系转化入口。",
                    "先看已知条件结构，再判断模块，再选方法。",
                    "解三角形、概率统计、立体几何都很典型。",
                ],
            },
        },
        {
            "title": "长期记忆校验 / Long-Term Memory Check",
            "mixed": {
                "blanks": [
                    ("长期复习时，最该记住的不是零散答案，而是题型入口与____________、____________之间的对应关系。", "方法；得分点"),
                ],
                "choices": [
                    {
                        "question": "哪一项最符合本节课的长期目标 / Which best matches the long-term goal of the lesson?",
                        "options": [
                            "A. 只背结论 / Memorize conclusions only",
                            "B. 只记课堂原话 / Remember quotes only",
                            "C. 看到题目能先识别模块，再选方法和保分策略 / Recognize the module first, then choose method and score strategy",
                            "D. 只会一道代表题 / Only master one representative example",
                        ],
                        "answer": "C",
                    }
                ],
            },
            "oral": {
                "prompts": [
                    "为什么这节课最该留下的是“题型入口地图”而不是答案表？",
                    "如果只剩 1 分钟复盘，这节课你会先回想哪几个关键词？",
                    "请口头总结本节课最核心的 3 个易错提醒。",
                ],
                "keypoints": [
                    "因为入口决定方法，方法决定得分，答案不能迁移。",
                    "余弦定理、正弦图像、分布列、建系找点、抛物线转化。",
                    "别忽略多解判断、别混淆概率模型、别在计算上丢稳分。",
                ],
            },
        },
    ],
}


VARIANTS = {
    "cn": {
        "filename": "review-plan-chinese-only-quote-replay-default.pdf",
        "label": "中文版课后复习版",
        "language": "cn",
    },
    "hybrid": {
        "filename": "review-plan-bilingual-quotes-10-15-quote-replay-layout-hybrid-default.pdf",
        "label": "默认课后复习版 / Default Review Edition",
        "language": "bilingual",
    },
    "cn_preview": {
        "filename": "review-plan-chinese-only-quote-replay-default.pdf",
        "label": "中文版课后复习版",
        "language": "cn",
    },
}


LETTER_SPACING = 0.18
PORTABLE_FONT_NAME = "ReviewPlanCJK"
ACTIVE_FONT_NAME = "STSong-Light"

CIRCLED_DIGIT_REPLACEMENTS = {
    "①": "1.",
    "②": "2.",
    "③": "3.",
    "④": "4.",
    "⑤": "5.",
    "⑥": "6.",
    "⑦": "7.",
    "⑧": "8.",
    "⑨": "9.",
    "⑩": "10.",
}

PORTABLE_SYMBOL_REPLACEMENTS = (
    ("☐", "[ ]"),
    ("□", "[ ]"),
    ("✅", "[已完成]"),
    ("❌", "[未完成]"),
    ("📝", "题型"),
    ("📌", "提示："),
    ("⚠️", "注意："),
    ("⚠", "注意："),
    ("✏️", ""),
    ("✏", ""),
    ("•", "-"),
    ("▶", "-"),
    ("★", "-"),
    ("☆", "-"),
    ("→", "->"),
)
BARE_GREEK_NAME_REPLACEMENTS = {
    "alpha": "α",
    "beta": "β",
}

LATEX_BLOCK_DOLLAR_PATTERN = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL)
LATEX_INLINE_PATTERN = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$(?!\$)")
LATEX_PAREN_PATTERN = re.compile(r"\\{1,2}\((.+?)\\{1,2}\)")
LATEX_BRACKET_PATTERN = re.compile(r"\\{1,2}\[(.+?)\\{1,2}\]", re.DOTALL)
LATEX_SEGMENT_PATTERN = re.compile(
    r"(?<!\\)\$\$(.+?)(?<!\\)\$\$"
    r"|(?<!\\)\$(?!\$)(.+?)(?<!\\)\$(?!\$)"
    r"|\\{1,2}\((.+?)\\{1,2}\)"
    r"|\\{1,2}\[(.+?)\\{1,2}\]",
    re.DOTALL,
)
LATEX_COMMAND_REPLACEMENTS = (
    (r"\infty", "∞"),
    (r"\Rightarrow", "⇒"),
    (r"\Leftarrow", "⇐"),
    (r"\rightarrow", "XRRIGHTARROWTOKEN"),
    (r"\leftarrow", "XRLEFTARROWTOKEN"),
    (r"\subseteq", "⊆"),
    (r"\supseteq", "⊇"),
    (r"\subset", "⊂"),
    (r"\supset", "⊃"),
    (r"\notin", "∉"),
    (r"\approx", "≈"),
    (r"\geq", "≥"),
    (r"\ge", "≥"),
    (r"\leq", "≤"),
    (r"\le", "≤"),
    (r"\neq", "≠"),
    (r"\times", "×"),
    (r"\cdot", "·"),
    (r"\angle", "∠"),
    (r"\triangle", "△"),
    (r"\cong", "≌"),
    (r"\circ", "°"),
    (r"\perp", "⊥"),
    (r"\parallel", "∥"),
    (r"\ldots", "..."),
    (r"\cdots", "..."),
    (r"\dots", "..."),
    (r"\pm", "±"),
    (r"\div", "÷"),
    (r"\in", "∈"),
    (r"\to", "XRRIGHTARROWTOKEN"),
    (r"\left", ""),
    (r"\right", ""),
)
MATHBB_SET_MAP = {
    "C": "ℂ",
    "N": "ℕ",
    "Q": "ℚ",
    "R": "ℝ",
    "Z": "ℤ",
}
SUPERSCRIPT_TRANSLATION = str.maketrans({
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "+": "⁺",
    "-": "⁻",
    "=": "⁼",
    "(": "⁽",
    ")": "⁾",
    "n": "ⁿ",
    "i": "ⁱ",
})
# Extra superscript letters commonly used in Chinese math (combinations, sequences, etc.)
SUPERSCRIPT_LETTER_MAP = {
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ",
    "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "j": "ʲ", "k": "ᵏ",
    "l": "ˡ", "m": "ᵐ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ",
    "s": "ˢ", "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ",
    "x": "ˣ", "y": "ʸ",
}
def _render_superscript(content: str) -> str:
    result = []
    for c in content:
        translated = c.translate(SUPERSCRIPT_TRANSLATION)
        if translated != c:
            result.append(translated)
        elif c.lower() in SUPERSCRIPT_LETTER_MAP:
            result.append(SUPERSCRIPT_LETTER_MAP[c.lower()])
        else:
            result.append(c)
    return "".join(result)


def _render_subscript(content: str) -> str:
    compact = str(content or "").strip()
    if re.fullmatch(r"[A-Za-z0-9]+", compact):
        return f"_{compact}" if len(compact) == 1 else f"_{{{compact}}}"

    # Complex subscripts such as limits are easier to read as an inline condition.
    return f"_({content})"


BROKEN_NEWLINE_LATEX_COMMAND_PATTERN = re.compile(
    r"(?<![。！？.!?：:；;])\n(?=(?:eq\b|otin\b|abla\b|mid\b|parallel\b|subset(?:eq)?\b|supset(?:eq)?\b|rightarrow\b|leftarrow\b|Rightarrow\b|Leftarrow\b|iff\b))"
)
LATEX_CASES_PATTERN = re.compile(r"\\begin\s*\{\s*cases\s*\}([\s\S]*?)\\end\s*\{\s*cases\s*\}")
LATEX_UNDERLINED_SPACE_PATTERN = re.compile(r"\\underline\s*\{\s*\\hspace\s*\{[^{}]*\}\s*\}")
LATEX_UNDERLINED_PHANTOM_PATTERN = re.compile(r"\\underline\s*\{\s*\\phantom\s*\{[^{}]*\}\s*\}")
LATEX_HSPACE_PATTERN = re.compile(r"\\hspace\s*\{[^{}]*\}")
LATEX_VISUAL_RENDER_PATTERN = re.compile(r"\S")

_MATHTEXT_MODULE: Any | None = None
_MATHTEXT_IMPORT_FAILED = False
_MATHJAX_RENDER_FAILED = False


def _repair_latex_transport_controls(text: str) -> str:
    repaired = str(text or "").replace("\r\n", "\n")
    repaired = repaired.replace("\t", "\\t")
    repaired = repaired.replace("\f", "\\f")
    repaired = repaired.replace("\b", "\\b")
    repaired = repaired.replace("\r", "\\r")
    return BROKEN_NEWLINE_LATEX_COMMAND_PATTERN.sub(r"\\n", repaired)


def _normalize_latex_cases(text: str) -> str:
    def replace_cases(match: re.Match[str]) -> str:
        content = match.group(1)
        content = content.replace("\\\\", "\n").replace(r"\cr", "\n")
        rows = []
        for row in content.splitlines():
            clean = re.sub(r"\s*&\s*", "，", row).strip(" \t,，;；")
            if clean:
                rows.append(clean)
        return "； ".join(rows)

    return LATEX_CASES_PATTERN.sub(replace_cases, text)


def _normalize_latex_placeholders(text: str) -> str:
    normalized = LATEX_UNDERLINED_SPACE_PATTERN.sub("______", text)
    normalized = LATEX_UNDERLINED_PHANTOM_PATTERN.sub("______", normalized)
    normalized = LATEX_HSPACE_PATTERN.sub("______", normalized)
    normalized = re.sub(r"\\underline\s*\{([^{}]+)\}", r"\1", normalized)
    return normalized


def _normalize_latex_placeholders_for_mathtext(text: str) -> str:
    normalized = LATEX_UNDERLINED_SPACE_PATTERN.sub(r"\\_\\_\\_", text)
    normalized = LATEX_UNDERLINED_PHANTOM_PATTERN.sub(r"\\_\\_\\_", normalized)
    normalized = LATEX_HSPACE_PATTERN.sub(r"\\_\\_\\_", normalized)
    normalized = re.sub(r"\\underline\s*\{([^{}]+)\}", r"\1", normalized)
    return normalized


def _normalize_latex_structures(text: str) -> str:
    normalized = _normalize_latex_placeholders(text)
    normalized = _normalize_latex_cases(normalized)
    return normalized


def _normalize_bare_math_words(text: str) -> str:
    normalized = str(text or "")
    normalized = re.sub(r"\^\\?circ\b", "°", normalized)
    normalized = re.sub(
        r"(?<![A-Za-z\\])(?P<func>sin|cos|tan)\s*(?P<name>alpha|beta)(?![A-Za-z])",
        lambda match: f"{match.group('func').lower()}{BARE_GREEK_NAME_REPLACEMENTS[match.group('name').lower()]}",
        normalized,
        flags=re.IGNORECASE,
    )
    for source, target in BARE_GREEK_NAME_REPLACEMENTS.items():
        normalized = re.sub(rf"(?<![A-Za-z\\]){source}(?![A-Za-z])", target, normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"([=＝])\s*\(([0-9]+)\)\s*/\s*\(([0-9]+)\)", r"\1\2/\3", normalized)
    normalized = re.sub(r"(?<![A-Za-z\\])triangle\s*", "△", normalized)
    normalized = re.sub(r"(?<![A-Za-z\\])angle\s*", "∠", normalized)
    normalized = re.sub(r"(?<![A-Za-z\\])cong(?![A-Za-z])", "≌", normalized)
    normalized = re.sub(r"(?<![A-Za-z\\])perp(?![A-Za-z])", "⊥", normalized)
    normalized = re.sub(r"(?<![A-Za-z\\])parallel(?![A-Za-z])", "∥", normalized)
    return normalized


def _get_mathtext_module():
    global _MATHTEXT_MODULE, _MATHTEXT_IMPORT_FAILED
    if _MATHTEXT_MODULE is not None:
        return _MATHTEXT_MODULE
    if _MATHTEXT_IMPORT_FAILED:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import matplotlib

            matplotlib.use("Agg", force=True)
            from matplotlib import mathtext

        _MATHTEXT_MODULE = mathtext
        return _MATHTEXT_MODULE
    except Exception:
        _MATHTEXT_IMPORT_FAILED = True
        return None


def _latex_needs_visual_render(latex: str) -> bool:
    return bool(LATEX_VISUAL_RENDER_PATTERN.search(str(latex or "")))


def _mathjax_renderer_available() -> bool:
    if _MATHJAX_RENDER_FAILED:
        return False
    if not MATHJAX_RENDERER_SCRIPT.exists():
        return False
    node = shutil.which("node")
    if not node:
        return False
    return (REPO_ROOT / "frontend" / "node_modules" / "mathjax-full").exists()


@lru_cache(maxsize=512)
def _render_mathjax_svg(formula: str) -> str | None:
    global _MATHJAX_RENDER_FAILED
    if not _mathjax_renderer_available():
        return None

    node = shutil.which("node")
    if not node:
        return None
    payload = json.dumps({"formula": formula, "display": True}, ensure_ascii=False)
    try:
        completed = subprocess.run(
            [node, str(MATHJAX_RENDERER_SCRIPT)],
            input=payload,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(REPO_ROOT / "frontend"),
            timeout=8,
            check=True,
        )
        result = json.loads(completed.stdout or "{}")
    except subprocess.CalledProcessError as exc:
        if "ERR_MODULE_NOT_FOUND" in str(exc.stderr):
            _MATHJAX_RENDER_FAILED = True
        return None
    except Exception:
        return None

    svg = result.get("svg")
    return svg if isinstance(svg, str) and svg.strip() else None


def _svg_attr_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value)
    return float(match.group(1)) if match else None


def _parse_svg_transform(value: str | None) -> tuple[float, float, float, float, float, float] | None:
    if not value:
        return None

    matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def multiply(left, right):
        a, b, c, d, e, f = left
        g, h, i, j, k, l = right
        return (
            a * g + c * h,
            b * g + d * h,
            a * i + c * j,
            b * i + d * j,
            a * k + c * l + e,
            b * k + d * l + f,
        )

    for name, raw_args in re.findall(r"(matrix|translate|scale)\(([^)]*)\)", value):
        args = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?", raw_args, flags=re.IGNORECASE)]
        if name == "matrix" and len(args) == 6:
            current = tuple(args)
        elif name == "translate" and args:
            current = (1.0, 0.0, 0.0, 1.0, args[0], args[1] if len(args) > 1 else 0.0)
        elif name == "scale" and args:
            current = (args[0], 0.0, 0.0, args[1] if len(args) > 1 else args[0], 0.0, 0.0)
        else:
            continue
        matrix = multiply(matrix, current)
    return matrix


def _svg_children_to_group(element: ElementTree.Element, fill_color) -> Group:
    group = Group()
    transform = _parse_svg_transform(element.attrib.get("transform"))
    if transform is not None:
        group.transform = transform

    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "path":
            path_data = child.attrib.get("d", "")
            if not path_data:
                continue
            path = SvgPath(path_data, fillColor=fill_color, strokeColor=None)
            path_transform = _parse_svg_transform(child.attrib.get("transform"))
            if path_transform is not None:
                wrapper = Group(path)
                wrapper.transform = path_transform
                group.add(wrapper)
            else:
                group.add(path)
        elif tag == "rect":
            x = _svg_attr_number(child.attrib.get("x")) or 0
            y = _svg_attr_number(child.attrib.get("y")) or 0
            width = _svg_attr_number(child.attrib.get("width")) or 0
            height = _svg_attr_number(child.attrib.get("height")) or 0
            if width <= 0 or height <= 0:
                continue
            rect = Rect(x, y, width, height, fillColor=fill_color, strokeColor=None)
            rect_transform = _parse_svg_transform(child.attrib.get("transform"))
            if rect_transform is not None:
                wrapper = Group(rect)
                wrapper.transform = rect_transform
                group.add(wrapper)
            else:
                group.add(rect)
        elif tag in {"g", "svg"}:
            nested = _svg_children_to_group(child, fill_color)
            if nested.contents:
                group.add(nested)
    return group


def _mathjax_svg_to_drawing(svg: str, font_size: float, color: Any, max_width: float) -> Drawing | None:
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError:
        return None

    svg_element = root if root.tag.rsplit("}", 1)[-1] == "svg" else root.find(".//{http://www.w3.org/2000/svg}svg")
    if svg_element is None:
        return None
    view_box = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", svg_element.attrib.get("viewBox", ""))]
    if len(view_box) != 4 or view_box[2] <= 0 or view_box[3] <= 0:
        return None

    min_x, min_y, view_width, view_height = view_box
    width = view_width / 1000.0 * font_size
    height = view_height / 1000.0 * font_size
    attr_width = _svg_attr_number(svg_element.attrib.get("width"))
    attr_height = _svg_attr_number(svg_element.attrib.get("height"))
    if attr_width and svg_element.attrib.get("width", "").endswith("em"):
        width = attr_width * font_size
    if attr_height and svg_element.attrib.get("height", "").endswith("em"):
        height = attr_height * font_size
    if width <= 0 or height <= 0:
        return None

    scale = width / view_width
    if width > max_width:
        fit_scale = max_width / width
        width *= fit_scale
        height *= fit_scale
        scale *= fit_scale

    fill_color = colors.HexColor(_normalize_formula_color_hex(color))
    content = _svg_children_to_group(svg_element, fill_color)
    content.transform = (scale, 0.0, 0.0, -scale, -min_x * scale, (min_y + view_height) * scale)
    drawing = Drawing(width, height)
    drawing.add(content)
    return drawing


def _render_mathjax_formula_drawing(latex: str, max_width: float, font_size: float, color: Any) -> Drawing | None:
    prepared = _prepare_latex_for_mathtext(latex)
    svg = _render_mathjax_svg(prepared)
    if svg is None:
        return None
    return _mathjax_svg_to_drawing(svg, font_size, color, max_width)


def _prepare_latex_for_mathtext(latex: str) -> str:
    prepared = _repair_latex_transport_controls(latex).strip()
    prepared = re.sub(r"\\\\(?=[A-Za-z])", r"\\", prepared)
    prepared = _normalize_latex_placeholders_for_mathtext(prepared)
    prepared = re.sub(r"\\ge(?![A-Za-z])", r"\\geq", prepared)
    prepared = re.sub(r"\\le(?![A-Za-z])", r"\\leq", prepared)
    prepared = prepared.replace(r"\dfrac", r"\frac")
    return prepared


def _normalize_formula_color_hex(value: Any) -> str:
    if value is None:
        return FORMULA_DEFAULT_COLOR
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
            return text.upper()
        try:
            value = colors.toColor(text)
        except Exception:
            return FORMULA_DEFAULT_COLOR

    red = getattr(value, "red", None)
    green = getattr(value, "green", None)
    blue = getattr(value, "blue", None)
    if red is None or green is None or blue is None:
        return FORMULA_DEFAULT_COLOR
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, round(float(red) * 255))),
        max(0, min(255, round(float(green) * 255))),
        max(0, min(255, round(float(blue) * 255))),
    )


def _style_formula_font_size(style) -> float:
    font_size = getattr(style, "fontSize", FORMULA_DEFAULT_FONT_SIZE)
    try:
        return max(1.0, float(font_size))
    except (TypeError, ValueError):
        return FORMULA_DEFAULT_FONT_SIZE


def _make_formula_png_transparent(buffer: BytesIO, color_hex: str) -> tuple[BytesIO, int, int]:
    from PIL import Image as PILImage

    buffer.seek(0)
    with PILImage.open(buffer) as image:
        rgba = image.convert("RGBA")

    target = colors.HexColor(color_hex)
    target_rgb = (
        max(0, min(255, round(float(target.red) * 255))),
        max(0, min(255, round(float(target.green) * 255))),
        max(0, min(255, round(float(target.blue) * 255))),
    )
    pixels = []
    for red, green, blue, alpha in rgba.getdata():
        luminance = int(red * 0.299 + green * 0.587 + blue * 0.114)
        ink_alpha = max(0, min(255, 255 - luminance))
        if ink_alpha < 9 or alpha == 0:
            pixels.append((target_rgb[0], target_rgb[1], target_rgb[2], 0))
        else:
            pixels.append((target_rgb[0], target_rgb[1], target_rgb[2], min(alpha, ink_alpha)))
    rgba.putdata(pixels)

    bbox = rgba.getbbox()
    if bbox is not None:
        left, top, right, bottom = bbox
        padding = 2
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(rgba.width, right + padding)
        bottom = min(rgba.height, bottom + padding)
        rgba = rgba.crop((left, top, right, bottom))

    output = BytesIO()
    rgba.save(output, format="PNG")
    output.seek(0)
    return output, rgba.width, rgba.height


@lru_cache(maxsize=512)
def _render_latex_formula_png_bytes(prepared: str, dpi: int, font_size: float, color_hex: str) -> tuple[bytes, int, int] | None:
    mathtext = _get_mathtext_module()
    if mathtext is None:
        return None

    buffer = BytesIO()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from matplotlib.font_manager import FontProperties

            mathtext.math_to_image(
                f"${prepared}$",
                buffer,
                dpi=dpi,
                format="png",
                prop=FontProperties(size=font_size),
            )
        buffer, width_px, height_px = _make_formula_png_transparent(buffer, color_hex)
    except Exception:
        return None
    return buffer.getvalue(), width_px, height_px


def render_latex_formula_flowable(
    latex: str,
    max_width: float = 150 * mm,
    *,
    dpi: int = FORMULA_DPI,
    font_size: float = FORMULA_DEFAULT_FONT_SIZE,
    color: Any = FORMULA_DEFAULT_COLOR,
) -> Flowable | None:
    if not _latex_needs_visual_render(latex):
        return None

    mathjax_formula = _render_mathjax_formula_drawing(latex, max_width, font_size, color)
    if mathjax_formula is not None:
        return mathjax_formula

    prepared = _prepare_latex_for_mathtext(latex)
    color_hex = _normalize_formula_color_hex(color)
    rendered = _render_latex_formula_png_bytes(prepared, dpi, font_size, color_hex)
    if rendered is None:
        return None
    png_bytes, width_px, height_px = rendered
    buffer = BytesIO(png_bytes)

    width = max(1.0, width_px / dpi * 72)
    height = max(1.0, height_px / dpi * 72)
    if width > max_width:
        scale = max_width / width
        width *= scale
        height *= scale

    formula = Image(buffer, width=width, height=height)
    formula.hAlign = "LEFT"
    return formula


def _normalize_bare_latex_text(text: str) -> str:
    normalized = str(text or "").replace(r"\$", "$")
    normalized = re.sub(r"\\\\(?=[A-Za-z])", r"\\", normalized)
    normalized = re.sub(r"\\+_", "XRUNDERSCORETOKEN", normalized)
    normalized = _normalize_latex_structures(normalized)
    normalized = _normalize_bare_math_words(normalized)

    for _ in range(5):
        next_value = re.sub(
            r"\\frac\{([^{}]+)\}\{([^{}]+)\}",
            r"(\1)/(\2)",
            normalized,
        )
        next_value = re.sub(
            r"\\sqrt\{([^{}]+)\}",
            r"√(\1)",
            next_value,
        )
        if next_value == normalized:
            break
        normalized = next_value

    normalized = re.sub(r"\\text\{([^{}]+)\}", r"\1", normalized)
    normalized = re.sub(
        r"\\mathbb\s*\{?([A-Za-z])\}?",
        lambda match: MATHBB_SET_MAP.get(match.group(1), match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r"\^\{([^{}]+)\}",
        lambda match: _render_superscript(match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r"\^([0-9n()+\-=i])",
        lambda match: _render_superscript(match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r"\^([a-zA-Z])",
        lambda match: _render_superscript(match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r"_\{([^{}]+)\}",
        lambda match: _render_subscript(match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r"_([a-zA-Z0-9])",
        lambda match: _render_subscript(match.group(1)),
        normalized,
    )

    for source, target in LATEX_COMMAND_REPLACEMENTS:
        normalized = normalized.replace(source, target)

    normalized = _normalize_bare_math_words(normalized)
    normalized = normalized.replace("XRUNDERSCORETOKEN", "_")
    return normalized


class TrackingCanvas(Canvas):
    def __init__(self, *args, char_space=0, **kwargs):
        self._char_space = char_space
        super().__init__(*args, **kwargs)

    def beginText(self, x=0, y=0, direction=None):
        text_object = super().beginText(x, y, direction)
        if self._char_space:
            text_object.setCharSpace(self._char_space)
        return text_object


def _format_latex_math_segment(text):
    # Some inputs may contain double-escaped latex commands from JSON/text transport.
    normalized = _repair_latex_transport_controls(text)
    normalized = _normalize_latex_structures(normalized)
    normalized = normalized.replace("\\\\", "\\")
    normalized = _normalize_bare_latex_text(normalized)
    normalized = re.sub(r"\\([A-Za-z]+)", lambda match: match.group(1), normalized)
    normalized = re.sub(r"\\([{}()\[\]])", r"\1", normalized)
    normalized = normalized.replace("\\", "")
    normalized = normalized.replace("{", "").replace("}", "")
    normalized = re.sub(r"\s*([≥≤≠=<>])\s*", r"\1", normalized)
    normalized = normalized.replace("lim_(", "lim(")
    return normalized.strip()


def _normalize_inline_latex(value):
    value = _repair_latex_transport_controls(value)
    normalized = LATEX_BLOCK_DOLLAR_PATTERN.sub(
        lambda match: _format_latex_math_segment(match.group(1)),
        value,
    )
    normalized = LATEX_INLINE_PATTERN.sub(
        lambda match: _format_latex_math_segment(match.group(1)),
        normalized,
    )
    normalized = LATEX_PAREN_PATTERN.sub(
        lambda match: _format_latex_math_segment(match.group(1)),
        normalized,
    )
    normalized = LATEX_BRACKET_PATTERN.sub(
        lambda match: _format_latex_math_segment(match.group(1)),
        normalized,
    )
    # Strip markdown bold/italic wrappers that may surround math or text
    normalized = re.sub(r"\*\*(.+?)\*\*", r"\1", normalized)
    normalized = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", normalized)
    normalized = _normalize_bare_latex_text(normalized)
    return normalized.replace("lim_(", "lim(")


def build_timestamped_output_path(output_dir, filename):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_path = output_dir / filename
    return base_path.with_name(f"{base_path.stem}-{timestamp}{base_path.suffix}")


def make_safe_filename_part(value, fallback="课程复习计划", max_length=80):
    normalized = localize_text(str(value or ""), True)
    normalized = re.sub(r"^[\d一二三四五六七八九十]+[.、]\s*", "", normalized)
    normalized = re.sub(r"[\\/:*?\"<>|：]+", "-", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-. ")
    if not normalized:
        normalized = fallback
    return normalized[:max_length].strip("-. ") or fallback


def build_lesson_filename_part(lesson, fallback="课程复习计划"):
    title = lesson.get("title", "") if isinstance(lesson, dict) else ""
    title = re.sub(r"(课后)?复习计划$", "", str(title or ""))
    safe_title = make_safe_filename_part(title, "", 80)
    if len(safe_title) > 5:
        return safe_title

    topics = []
    for topic in lesson.get("full_review_topics", []) if isinstance(lesson, dict) else []:
        safe_topic = make_safe_filename_part(topic, "", 24)
        if safe_topic and safe_topic not in topics:
            topics.append(safe_topic)
        if len(topics) >= 3:
            break
    if topics:
        return make_safe_filename_part("-".join(topics), fallback)

    return make_safe_filename_part(title, fallback)


def is_chinese_only(variant_key):
    return VARIANTS[variant_key].get("language") == "cn"


def load_lesson_pack(pack_path):
    global LESSON, DAYS, KNOWLEDGE_SECTIONS, FINAL_REMINDER_LINES

    resolved_path = Path(pack_path)
    if not resolved_path.is_absolute():
        resolved_path = (ROOT / resolved_path).resolve()
    if not resolved_path.exists():
        raise SystemExit(f"Lesson pack not found: {resolved_path}")

    spec = importlib.util.spec_from_file_location("lesson_pack", resolved_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load lesson pack: {resolved_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    required = ["LESSON", "DAYS", "KNOWLEDGE_SECTIONS"]
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        raise SystemExit(f"Lesson pack missing required fields: {', '.join(missing)}")

    LESSON = module.LESSON
    DAYS = module.DAYS
    KNOWLEDGE_SECTIONS = module.KNOWLEDGE_SECTIONS
    FINAL_REMINDER_LINES = getattr(module, "FINAL_REMINDER_LINES", FINAL_REMINDER_LINES)


def normalize_portable_text(value):
    if not isinstance(value, str):
        return value

    normalized = _normalize_inline_latex(value)
    normalized = re.sub(r"[👩👨]\u200d?🏫\s*老师追问[:：]?\s*", "老师追问：", normalized)
    normalized = re.sub(r"[👩👨]\u200d?🏫\s*老师问[:：]?\s*", "老师问：", normalized)
    normalized = re.sub(r"[👩👨]\u200d?🏫\s*", "老师", normalized)

    for source, target in CIRCLED_DIGIT_REPLACEMENTS.items():
        normalized = normalized.replace(source, target)
    for source, target in PORTABLE_SYMBOL_REPLACEMENTS:
        normalized = normalized.replace(source, target)

    normalized = re.sub(r"([：:])\s+", r"\1", normalized)
    normalized = re.sub(r"[ \t\r\f\v]*\n[ \t\r\f\v]*", " ", normalized)
    normalized = re.sub(r"\s{2,}", " ", normalized)
    normalized = re.sub(r"(^|\s)-\s*", r"\1- ", normalized)
    normalized = normalized.replace("XRRIGHTARROWTOKEN", "→")
    normalized = normalized.replace("XRLEFTARROWTOKEN", "←")
    return normalized.strip()


def normalize_portable_text_preserving_latex(value):
    if not isinstance(value, str):
        return value

    pieces = []
    for kind, segment in _split_latex_segments(value):
        if kind == "latex":
            pieces.append(f"${_repair_latex_transport_controls(segment).strip()}$")
        else:
            pieces.append(normalize_portable_text(segment))
    return "".join(pieces).strip()


def localize_text(value, chinese_only):
    if not isinstance(value, str):
        return value

    if not chinese_only:
        return normalize_portable_text(value)

    localized = value.split(" / ", 1)[0].strip()
    localized = re.sub(r"([。！？）】』”])\s*[A-Za-z][\s\S]*$", r"\1", localized)
    return normalize_portable_text(localized.strip())


def localize_lines(values, chinese_only):
    return [localize_text(value, chinese_only) for value in values]


def paragraph_safe_text(value):
    return escape(normalize_portable_text(str(value or "")))


def localize_paragraph_text(value, chinese_only):
    return escape(localize_text(value, chinese_only))


def _localize_raw_text(value, chinese_only):
    if not isinstance(value, str):
        return str(value or "")

    if not chinese_only:
        return value

    localized = value.split(" / ", 1)[0].strip()
    return re.sub(r"([。！？）】』”])\s*[A-Za-z][\s\S]*$", r"\1", localized)


def _split_latex_segments(value: str):
    position = 0
    for match in LATEX_SEGMENT_PATTERN.finditer(value):
        if match.start() > position:
            yield "text", value[position:match.start()]
        latex = next((group for group in match.groups() if group is not None), "")
        yield "latex", latex
        position = match.end()
    if position < len(value):
        yield "text", value[position:]


def _split_latex_segments_with_spans(value: str):
    position = 0
    for match in LATEX_SEGMENT_PATTERN.finditer(value):
        if match.start() > position:
            yield "text", value[position:match.start()], position, match.start()
        latex = next((group for group in match.groups() if group is not None), "")
        yield "latex", latex, match.start(), match.end()
        position = match.end()
    if position < len(value):
        yield "text", value[position:], position, len(value)


def _latex_is_display_context(raw: str, start: int, end: int) -> bool:
    before = raw[:start]
    after = raw[end:]
    before = re.sub(r"^\s*(?:[-•]\s*)?(?:\d+\.\s*)?(?:[A-D][.．]\s*)?", "", before).strip()
    after = after.strip()
    return not before and bool(re.fullmatch(r"[。！？.!?，,；;：:、）】』”]*", after))


def _paragraph_from_text(value: str, style) -> Paragraph | None:
    text = value.strip()
    if not text:
        return None
    return Paragraph(escape(text), style)


def rich_text_flowables(
    value,
    style,
    chinese_only=False,
    *,
    max_width: float = 150 * mm,
    render_display_formulas: bool = True,
) -> list[Flowable]:
    raw = _localize_raw_text(str(value or ""), chinese_only).strip()
    if not raw:
        return [Paragraph("", style)]

    parts: list[tuple[str, str | Flowable]] = []
    saw_rendered_formula = False
    formula_font_size = _style_formula_font_size(style)
    formula_color = getattr(style, "textColor", FORMULA_DEFAULT_COLOR)
    for kind, segment, start, end in _split_latex_segments_with_spans(raw):
        if kind == "latex":
            if render_display_formulas and _latex_is_display_context(raw, start, end):
                formula = render_latex_formula_flowable(
                    segment,
                    max_width=max_width,
                    font_size=formula_font_size,
                    color=formula_color,
                )
                if formula is not None:
                    parts.append(("formula", formula))
                    parts.append(("spacer", Spacer(1, 0.45 * mm)))
                    saw_rendered_formula = True
                    continue
            parts.append(("text", _format_latex_math_segment(segment)))
        else:
            parts.append(("text", normalize_portable_text(segment)))

    if not saw_rendered_formula:
        combined = "".join(str(part) for kind, part in parts if kind == "text").strip()
        return [_paragraph_from_text(combined, style) or Paragraph("", style)]

    flowables: list[Flowable] = []
    pending_text = ""
    for kind, part in parts:
        if kind == "text":
            text = str(part)
            if re.fullmatch(r"[。！？.!?，,；;：:、]+", text.strip()):
                continue
            pending_text += text
            continue
        paragraph = _paragraph_from_text(pending_text, style)
        if paragraph is not None:
            flowables.append(paragraph)
            pending_text = ""
        if kind == "formula":
            if flowables:
                flowables.append(Spacer(1, 0.4 * mm))
            flowables.append(part)  # type: ignore[arg-type]
        elif kind == "spacer":
            flowables.append(part)  # type: ignore[arg-type]
    paragraph = _paragraph_from_text(pending_text, style)
    if paragraph is not None:
        flowables.append(paragraph)

    return flowables or [Paragraph(localize_paragraph_text(value, chinese_only), style)]


def rich_bullet_flowables(
    items,
    style,
    chinese_only=False,
    *,
    max_width: float = 150 * mm,
    render_display_formulas: bool = True,
) -> list[Flowable]:
    flowables: list[Flowable] = []
    for item in items:
        if flowables:
            flowables.append(Spacer(1, 0.6 * mm))
        flowables.extend(
            rich_text_flowables(
                f"- {item}",
                style,
                chinese_only,
                max_width=max_width,
                render_display_formulas=render_display_formulas,
            )
        )
    return flowables or [Paragraph("", style)]


def rich_numbered_flowables(
    items,
    style,
    chinese_only=False,
    *,
    max_width: float = 150 * mm,
    render_display_formulas: bool = False,
) -> list[Flowable]:
    flowables: list[Flowable] = []
    for index, item in enumerate(items, start=1):
        if flowables:
            flowables.append(Spacer(1, 0.8 * mm))
        flowables.extend(
            rich_text_flowables(
                f"{index}. {item}",
                style,
                chinese_only,
                max_width=max_width,
                render_display_formulas=render_display_formulas,
            )
        )
    return flowables or [Paragraph("", style)]


def localize_paragraph_lines(values, chinese_only):
    return [localize_paragraph_text(value, chinese_only) for value in values]


def localize_choice_option_lines(values, chinese_only):
    lines = []
    for value in values:
        text = localize_paragraph_text(value, chinese_only)
        lines.append(text.replace("； ", "；<br/>"))
    return lines


def choice_options_need_full_width(options, chinese_only):
    for option in options:
        localized = localize_text(option, chinese_only)
        if "；" in localized or "\\begin{cases}" in str(option):
            return True
        if len(re.sub(r"\s+", "", localized)) > 44:
            return True
    return False


def build_labels(chinese_only):
    if chinese_only:
        return {
            "date": "日期",
            "version": "版本",
            "quote_ratio": "原话比例",
            "layout": "页面风格",
            "day_zero": "第1天",
            "audience": "使用对象",
            "duration": "单次时长",
            "usage_title": "使用说明",
            "usage_text": "每一个复习日都要完整复习整节课内容。",
            "coverage_title": "全课覆盖清单",
            "quotes_title": "上课金句回顾",
            "goal": "复习目标",
            "focus": "复习聚焦",
            "tasks_title": "执行清单",
            "blanks_title": "填空题",
            "choices_title": "选择题",
            "knowledge_mixed_title": "课堂方法复盘",
            "knowledge_oral_title": "老师追问口述卡片",
            "teacher_quote_title": "课堂原话",
            "quote_replay_title": "课堂原话回放",
            "quote_replay_text": "先回想老师当时怎么画图、怎么强调方法选择、怎么提醒定义域，再动笔。",
            "check_text": "<b>完成打卡：</b> [ ] 我已完整复习整节课  [ ] 我已完成填空  [ ] 我已完成选择  [ ] 我已口头复述方法",
            "final_reminder": "总提醒",
            "final_reminder_box": "30天后应留下的内容",
            "answer_key": "自查答案",
            "answer_type": "题型",
            "answer_value": "答案",
            "blank_prefix": "填空",
            "choice_prefix": "选择",
            "reference_value": "参考",
            "knowledge_answer_mixed": "课堂方法参考答案",
            "knowledge_answer_oral": "口述参考要点",
            "oral_prompt_prefix": "提问",
            "footer_right": "课后复习计划 | 第{page}页",
        }

    return {
        "date": "Date",
        "version": "版本 / Version",
        "quote_ratio": "原话比例 / Quote Ratio",
        "layout": "页面风格 / Layout",
        "day_zero": "第1天 / Day 1",
        "audience": "使用对象 / Audience",
        "duration": "单次时长 / Duration",
        "usage_title": "使用说明 / Usage",
        "usage_text": "每一个复习日都要完整复习整节课内容。Each review day must revisit the whole lesson, not just one segment.",
        "coverage_title": "全课覆盖清单 / Full Lesson Coverage",
        "quotes_title": "上课金句回顾 / Class Quote Review",
        "goal": "复习目标 / Goal",
        "focus": "复习聚焦 / Focus",
        "tasks_title": "执行清单 / Tasks",
        "blanks_title": "填空题 / Blank Filling",
        "choices_title": "选择题 / Multiple Choice",
        "knowledge_mixed_title": "课堂方法复盘 / Method Review",
        "knowledge_oral_title": "老师追问卡片 / Teacher Oral Prompt Cards",
        "teacher_quote_title": "课堂原话 / Teacher Quote",
        "quote_replay_title": "课堂原话回放 / Quote Replay",
        "quote_replay_text": "先回想老师当时怎么画图、怎么强调方法选择、怎么提醒定义域，再动笔。Replay the teacher's visual explanation and warnings before writing.",
        "check_text": "<b>完成打卡 / Check:</b> [ ] 我已完整复习整节课  [ ] 我已完成填空  [ ] 我已完成选择  [ ] 我已口头复述方法",
        "final_reminder": "总提醒 / Final Reminder",
        "final_reminder_box": "30 天后应留下的内容 / What Should Remain After 30 Days",
        "answer_key": "自查答案 / Answer Key",
        "answer_type": "Type",
        "answer_value": "Answer",
        "blank_prefix": "Blank",
        "choice_prefix": "Choice",
        "reference_value": "Reference",
        "knowledge_answer_mixed": "课堂方法参考答案 / Method Review Answers",
        "knowledge_answer_oral": "口述参考要点 / Oral Reference Points",
        "oral_prompt_prefix": "Prompt",
        "footer_right": "Review Plan | Page {page}",
    }


def build_quote_replay_text(day, labels, chinese_only):
    quotes = []
    for quote in day.get("quotes", []):
        normalized_quote = normalize_portable_text(str(quote or "").strip())
        if normalized_quote and normalized_quote not in quotes:
            quotes.append(normalized_quote)

    if not quotes:
        return labels["quote_replay_text"]

    replay_intro = "先回想老师当时强调过的这几句，再动笔："
    if not chinese_only:
        replay_intro = "先回想老师当时强调过的这几句，再动笔。Replay these class cues before writing:"

    replay_lines = [
        f"{index}. {localize_paragraph_text(quote, chinese_only)}"
        for index, quote in enumerate(quotes[:2], start=1)
    ]
    return "<br/>".join([replay_intro, *replay_lines])


def build_quote_summary_text(quotes, chinese_only):
    normalized_quotes = []
    for quote in quotes:
        normalized_quote = normalize_portable_text(str(quote or "").strip())
        if normalized_quote and normalized_quote not in normalized_quotes:
            normalized_quotes.append(normalized_quote)

    quote_lines = [
        f"{index}. “{localize_paragraph_text(quote, chinese_only)}”"
        for index, quote in enumerate(normalized_quotes, start=1)
    ]
    return "<br/>".join(quote_lines)


def knowledge_mode_for_day(day, variant_key):
    if variant_key == "mixed":
        return "mixed"
    if variant_key == "oral":
        return "oral"

    offset = day["offset"]
    if offset in {1, 2, 30}:
        return "mixed"
    if offset in {7, 14}:
        return "oral"
    return "mixed"


def _portable_font_candidates():
    system = platform.system()
    if system == "Darwin":
        return [
            ("/System/Library/Fonts/PingFang.ttc", 0),
            ("/System/Library/Fonts/STHeiti Light.ttc", 0),
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
            ("/Library/Fonts/Arial Unicode.ttf", None),
        ]
    if system == "Windows":
        return [
            ("C:/Windows/Fonts/msyh.ttc", 0),
            ("C:/Windows/Fonts/msyhl.ttc", 0),
            ("C:/Windows/Fonts/simhei.ttf", None),
            ("C:/Windows/Fonts/simsun.ttc", 0),
        ]
    return [
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
    ]


def register_fonts():
    global ACTIVE_FONT_NAME

    registered_fonts = set(pdfmetrics.getRegisteredFontNames())
    if PORTABLE_FONT_NAME in registered_fonts:
        ACTIVE_FONT_NAME = PORTABLE_FONT_NAME
        return
    if "STSong-Light" in registered_fonts:
        ACTIVE_FONT_NAME = "STSong-Light"

    for font_path, subfont_index in _portable_font_candidates():
        if not Path(font_path).exists():
            continue
        try:
            if subfont_index is None:
                registerFont(TTFont(PORTABLE_FONT_NAME, font_path))
            else:
                registerFont(TTFont(PORTABLE_FONT_NAME, font_path, subfontIndex=subfont_index))
            ACTIVE_FONT_NAME = PORTABLE_FONT_NAME
            return
        except Exception:
            continue

    if "STSong-Light" not in registered_fonts:
        registerFont(UnicodeCIDFont("STSong-Light"))
    ACTIVE_FONT_NAME = "STSong-Light"


def format_iso_date(value):
    return value.strftime("%Y-%m-%d")


def review_date_for_day(base_date, day):
    day_number = max(1, int(day.get("offset", 1)))
    return base_date + timedelta(days=day_number - 1)


def build_day_heading(day, base_date, chinese_only=False):
    review_date = review_date_for_day(base_date, day)
    day_label = localize_text(day["day"], chinese_only)
    if chinese_only:
        return f"{day_label}  |  日期：{format_iso_date(review_date)}"
    return f"{day_label}  |  Date: {format_iso_date(review_date)}"


def max_review_day(days):
    day_numbers = []
    for day in days or []:
        try:
            day_numbers.append(max(1, int(day.get("offset", 1))))
        except Exception:
            continue
    return max(day_numbers or [30])


def adapt_labels_for_review_schedule(labels, days, chinese_only):
    if not chinese_only:
        return labels
    review_day = max_review_day(days)
    labels = dict(labels)
    if review_day <= 1:
        labels["usage_text"] = "当天完成本节课复习：先回忆课堂主线，再完成题目和自查。"
        labels["final_reminder_box"] = "当天复习后应留下的内容"
    elif review_day < 30:
        labels["final_reminder_box"] = f"{review_day}天复习后应留下的内容"
    return labels


def load_unified_review_plan_style_config() -> dict[str, Any]:
    style_path = ROOT.parent / "review_plan_workflow" / "prompts" / "styles" / "review_plan_style.yaml"
    if not style_path.exists():
        return {}
    try:
        import yaml

        payload = yaml.safe_load(style_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _palette_color(style_config: dict[str, Any], key: str, fallback: str):
    palette = style_config.get("palette") if isinstance(style_config.get("palette"), dict) else {}
    value = str(palette.get(key) or fallback)
    try:
        return colors.HexColor(value)
    except Exception:
        return colors.HexColor(fallback)


def _resolve_brand_logo(style_config: dict[str, Any]) -> Path | None:
    brand = style_config.get("brand") if isinstance(style_config.get("brand"), dict) else {}
    raw_path = str(brand.get("logo_path") or "").strip()
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT.parent / path
    return path if path.exists() else None


def _brand_name(style_config: dict[str, Any]) -> str:
    brand = style_config.get("brand") if isinstance(style_config.get("brand"), dict) else {}
    return str(brand.get("name") or "星润教育").strip() or "星润教育"


def _page_metric(style_config: dict[str, Any], key: str, fallback_mm: float) -> float:
    page = style_config.get("page") if isinstance(style_config.get("page"), dict) else {}
    value = page.get(key, fallback_mm)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback_mm)


def _coerce_base_date(value) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    return date.today()


def build_styles(style_config: dict[str, Any] | None = None):
    style_config = style_config or load_unified_review_plan_style_config()
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "base",
        parent=styles["BodyText"],
        fontName=ACTIVE_FONT_NAME,
        fontSize=10.3,
        leading=15,
        textColor=_palette_color(style_config, "text", "#222222"),
        wordWrap="CJK",
    )
    accent = _palette_color(style_config, "accent", "#B86B4B")
    accent_secondary = _palette_color(style_config, "accent_secondary", "#E6C9B5")
    soft = _palette_color(style_config, "soft", "#F6EFE8")
    quote_bg = _palette_color(style_config, "quote_bg", "#FAF3EC")
    paper = _palette_color(style_config, "paper", "#FFFDF9")
    card = _palette_color(style_config, "card", "#FFF9F3")
    header_bg = _palette_color(style_config, "header_bg", "#F1E1D3")
    line = _palette_color(style_config, "line", "#D8B7A1")
    muted = _palette_color(style_config, "muted", "#7A6559")
    return {
        "accent": accent,
        "accent_secondary": accent_secondary,
        "soft": soft,
        "quote_bg": quote_bg,
        "paper": paper,
        "card": card,
        "header_bg": header_bg,
        "line": line,
        "muted": muted,
        "title": ParagraphStyle("title", parent=base, fontSize=20, leading=26, alignment=TA_CENTER, textColor=base.textColor),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=11, leading=16, alignment=TA_CENTER, textColor=muted),
        "brand": ParagraphStyle("brand", parent=base, fontSize=9.5, leading=14, alignment=TA_CENTER, textColor=accent),
        "h1": ParagraphStyle("h1", parent=base, fontSize=14.5, leading=20, textColor=base.textColor, spaceBefore=6, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base, fontSize=12, leading=17, textColor=base.textColor, spaceBefore=3, spaceAfter=3),
        "body": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8.6, leading=12, textColor=muted),
        "tiny": ParagraphStyle("tiny", parent=base, fontSize=6.7, leading=8.0, textColor=muted),
        "quote": ParagraphStyle("quote", parent=base, fontSize=10, leading=15, leftIndent=6, rightIndent=6),
    }


def bullet_paragraph(items, style):
    return Paragraph("<br/>".join([f"- {paragraph_safe_text(item)}" for item in items]), style)


def _box_body_rows(body, body_style):
    if isinstance(body, (list, tuple)):
        rows = []
        for item in body:
            if isinstance(item, Spacer):
                continue
            if isinstance(item, Flowable):
                rows.append([item])
            else:
                rows.append([Paragraph(paragraph_safe_text(item), body_style)])
        return rows or [[Paragraph("", body_style)]]
    return [[body]]


def make_box(title, body, styles, background):
    rows = [[Paragraph(f"<b>{title}</b>", styles["h2"])]]
    rows.extend(_box_body_rows(body, styles["body"]))
    box = Table(rows, colWidths=[170 * mm], repeatRows=1)
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), styles["header_bg"]),
                ("BACKGROUND", (0, 1), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, styles["line"]),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, styles["line"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 1.6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 1.6),
                ("TOPPADDING", (0, 1), (-1, 1), 6),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
            ]
        )
    )
    return box


def make_choice_table(choices, styles, chinese_only=False):
    rows = []
    spans = []
    for index, choice in enumerate(choices, start=1):
        question_flowables = rich_text_flowables(
            f"{index}. {choice['question']}",
            styles["body"],
            chinese_only,
            max_width=74 * mm,
        )
        option_flowables: list[Flowable] = []
        for option in choice["options"]:
            if option_flowables:
                option_flowables.append(Spacer(1, 0.5 * mm))
            option_flowables.extend(
                rich_text_flowables(
                    option,
                    styles["small"],
                    chinese_only,
                    max_width=72 * mm,
                )
            )
        if choice_options_need_full_width(choice["options"], chinese_only):
            spans.append(len(rows))
            rows.append([question_flowables + [Spacer(1, 1 * mm)] + option_flowables, ""])
        else:
            rows.append(
                [
                    question_flowables,
                    option_flowables,
                ]
            )
    table = Table(rows, colWidths=[80 * mm, 78 * mm])
    span_styles = [("SPAN", (0, row), (1, row)) for row in spans]
    table.setStyle(
        TableStyle(
            [
                *span_styles,
                ("BACKGROUND", (0, 0), (-1, -1), styles["card"]),
                ("BOX", (0, 0), (-1, -1), 0.5, styles["line"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, styles["line"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def make_answer_table(day, styles, labels):
    rows = [[Paragraph(labels["answer_type"], styles["small"]), Paragraph(labels["answer_value"], styles["small"])]]
    for index, item in enumerate(day["blanks"], start=1):
        rows.append([Paragraph(f"{labels['blank_prefix']} {index}", styles["small"]), Paragraph(paragraph_safe_text(item[1]), styles["small"])])
    for index, item in enumerate(day["choices"], start=1):
        rows.append([Paragraph(f"{labels['choice_prefix']} {index}", styles["small"]), Paragraph(paragraph_safe_text(item["answer"]), styles["small"])])
    table = Table(rows, colWidths=[34 * mm, 136 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), styles["header_bg"]),
                ("BACKGROUND", (0, 1), (-1, -1), styles["paper"]),
                ("BOX", (0, 0), (-1, -1), 0.5, styles["line"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, styles["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def make_knowledge_mixed_table(knowledge_items, styles, chinese_only=False):
    rows = []
    for item in knowledge_items:
        cell_flowables: list[Flowable] = [Paragraph(f"<b>{localize_paragraph_text(item['title'], chinese_only)}</b>", styles["body"])]
        for index, blank in enumerate(item["mixed"]["blanks"], start=1):
            cell_flowables.append(Spacer(1, 1 * mm))
            cell_flowables.extend(
                rich_text_flowables(
                    f"填空 {index}. {blank[0]}",
                    styles["body"],
                    chinese_only,
                    max_width=150 * mm,
                )
            )
        for index, choice in enumerate(item["mixed"]["choices"], start=1):
            cell_flowables.append(Spacer(1, 1 * mm))
            cell_flowables.extend(
                rich_text_flowables(
                    f"选择 {index}. {choice['question']}",
                    styles["body"],
                    chinese_only,
                    max_width=150 * mm,
                )
            )
            for option in choice["options"]:
                cell_flowables.extend(
                    rich_text_flowables(
                        option,
                        styles["body"],
                        chinese_only,
                        max_width=150 * mm,
                    )
                )
        rows.append([cell_flowables])
    table = Table(rows, colWidths=[158 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), styles["card"]),
                ("BOX", (0, 0), (-1, -1), 0.5, styles["line"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, styles["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def make_knowledge_oral_table(knowledge_items, styles, chinese_only=False):
    rows = []
    for item in knowledge_items:
        prompt_lines = [f"<b>{localize_paragraph_text(item['title'], chinese_only)}</b>"]
        for index, prompt in enumerate(item["oral"]["prompts"], start=1):
            prompt_lines.append(f"提问 {index}. {localize_paragraph_text(prompt, chinese_only)}")
        rows.append([Paragraph("<br/><br/>".join(prompt_lines), styles["body"])])
    table = Table(rows, colWidths=[158 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), styles["card"]),
                ("BOX", (0, 0), (-1, -1), 0.5, styles["line"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, styles["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def make_knowledge_answer_table(knowledge_items, styles, knowledge_mode, labels, chinese_only=False):
    rows = [[Paragraph(labels["answer_type"], styles["small"]), Paragraph(labels["reference_value"], styles["small"])]]
    for item in knowledge_items:
        title = localize_text(item["title"], chinese_only)
        if knowledge_mode == "mixed":
            for index, blank in enumerate(item["mixed"]["blanks"], start=1):
                rows.append([Paragraph(paragraph_safe_text(f"{title} {labels['blank_prefix']} {index}"), styles["small"]), Paragraph(paragraph_safe_text(blank[1]), styles["small"])])
            for index, choice in enumerate(item["mixed"]["choices"], start=1):
                rows.append([Paragraph(paragraph_safe_text(f"{title} {labels['choice_prefix']} {index}"), styles["small"]), Paragraph(paragraph_safe_text(choice["answer"]), styles["small"])])
        else:
            for index, keypoint in enumerate(item["oral"]["keypoints"], start=1):
                rows.append([Paragraph(paragraph_safe_text(f"{title} {labels['oral_prompt_prefix']} {index}"), styles["small"]), Paragraph(localize_paragraph_text(keypoint, chinese_only), styles["small"])])
    table = Table(rows, colWidths=[50 * mm, 120 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), styles["header_bg"]),
                ("BACKGROUND", (0, 1), (-1, -1), styles["paper"]),
                ("BOX", (0, 0), (-1, -1), 0.5, styles["line"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, styles["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def make_compact_answer_key_table(days, knowledge_sections, styles, labels, variant_key, chinese_only=False):
    day_header = "复习日" if chinese_only else "Day"
    entries = []
    for day in days:
        day_label = localize_text(day["day"], chinese_only)
        for index, item in enumerate(day["blanks"], start=1):
            entries.append((day_label, f"{labels['blank_prefix']} {index}", paragraph_safe_text(item[1])))
        for index, item in enumerate(day["choices"], start=1):
            entries.append((day_label, f"{labels['choice_prefix']} {index}", paragraph_safe_text(item["answer"])))

        knowledge_items = knowledge_sections.get(day["day"], [])
        if not knowledge_items:
            continue
        knowledge_mode = knowledge_mode_for_day(day, variant_key)
        for item in knowledge_items:
            title = localize_text(item["title"], chinese_only)
            if knowledge_mode == "mixed":
                for index, blank in enumerate(item["mixed"]["blanks"], start=1):
                    entries.append((day_label, paragraph_safe_text(f"{title} {labels['blank_prefix']} {index}"), paragraph_safe_text(blank[1])))
                for index, choice in enumerate(item["mixed"]["choices"], start=1):
                    entries.append((day_label, paragraph_safe_text(f"{title} {labels['choice_prefix']} {index}"), paragraph_safe_text(choice["answer"])))
            else:
                for index, keypoint in enumerate(item["oral"]["keypoints"], start=1):
                    entries.append((day_label, paragraph_safe_text(f"{title} {labels['oral_prompt_prefix']} {index}"), localize_paragraph_text(keypoint, chinese_only)))

    split_at = (len(entries) + 1) // 2
    left_entries = entries[:split_at]
    right_entries = entries[split_at:]
    rows = [[
        Paragraph(day_header, styles["tiny"]),
        Paragraph(labels["answer_type"], styles["tiny"]),
        Paragraph(labels["answer_value"], styles["tiny"]),
        Paragraph(day_header, styles["tiny"]),
        Paragraph(labels["answer_type"], styles["tiny"]),
        Paragraph(labels["answer_value"], styles["tiny"]),
    ]]
    blank_cells = ["", "", ""]
    for index, left_entry in enumerate(left_entries):
        right_entry = right_entries[index] if index < len(right_entries) else blank_cells
        rows.append([
            Paragraph(paragraph_safe_text(left_entry[0]), styles["tiny"]),
            Paragraph(paragraph_safe_text(left_entry[1]), styles["tiny"]),
            Paragraph(left_entry[2], styles["tiny"]),
            Paragraph(paragraph_safe_text(right_entry[0]), styles["tiny"]),
            Paragraph(paragraph_safe_text(right_entry[1]), styles["tiny"]),
            Paragraph(right_entry[2], styles["tiny"]),
        ])

    table = Table(rows, colWidths=[15 * mm, 33 * mm, 37 * mm, 15 * mm, 33 * mm, 37 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), styles["header_bg"]),
                ("BACKGROUND", (0, 1), (-1, -1), styles["paper"]),
                ("BOX", (0, 0), (-1, -1), 0.5, styles["line"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, styles["line"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return table


def on_page(styles, variant_key, style_config=None, lesson_title=None):
    chinese_only = is_chinese_only(variant_key)
    labels = build_labels(chinese_only)
    footer_title = lesson_title or LESSON["title"]
    style_config = style_config or {}
    logo_path = _resolve_brand_logo(style_config)
    brand_name = _brand_name(style_config)

    def draw(canvas, doc):
        canvas.saveState()
        brand_logo_size = 8.5 * mm
        brand_top_y = A4[1] - 8 * mm
        brand_logo_y = brand_top_y - brand_logo_size
        brand_left_x = doc.leftMargin
        brand_text_x = brand_left_x
        brand_text_y = brand_logo_y + 2.7 * mm
        top_rule_y = A4[1] - 19 * mm

        if logo_path is not None:
            try:
                logo_reader = ImageReader(str(logo_path))
                canvas.drawImage(
                    logo_reader,
                    brand_left_x,
                    brand_logo_y,
                    width=brand_logo_size,
                    height=brand_logo_size,
                    mask="auto",
                    preserveAspectRatio=True,
                )
                brand_text_x = brand_left_x + brand_logo_size + 3 * mm
            except Exception:
                pass

        canvas.setFont(ACTIVE_FONT_NAME, 9.2)
        canvas.setFillColor(styles["accent"])
        canvas.drawString(brand_text_x, brand_text_y, brand_name)

        canvas.setStrokeColor(styles["line"])
        canvas.setLineWidth(0.8)
        canvas.line(doc.leftMargin, top_rule_y, A4[0] - doc.rightMargin, top_rule_y)
        canvas.setFont(ACTIVE_FONT_NAME, 8.5)
        canvas.setFillColor(styles["muted"])
        canvas.drawString(doc.leftMargin, 10 * mm, footer_title)
        canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, labels["footer_right"].format(page=canvas.getPageNumber()))
        canvas.restoreState()

    return draw


def build_story(styles, variant_key, *, lesson=None, days=None, final_reminder_lines=None, knowledge_sections=None, base_date=None, style_config=None):
    base_date = _coerce_base_date(base_date)
    chinese_only = is_chinese_only(variant_key)
    lesson = lesson or LESSON
    days = days or DAYS
    labels = adapt_labels_for_review_schedule(build_labels(chinese_only), days, chinese_only)
    final_reminder_lines = final_reminder_lines or FINAL_REMINDER_LINES
    knowledge_sections = knowledge_sections if knowledge_sections is not None else KNOWLEDGE_SECTIONS
    style_config = style_config or {}
    story = []
    logo_path = _resolve_brand_logo(style_config)
    story.append(Spacer(1, 6 * mm))
    if logo_path is not None:
        story.append(Image(str(logo_path), width=24 * mm, height=24 * mm, kind="proportional", mask="auto", hAlign="CENTER"))
        story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("星润课后复习计划", styles["brand"]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(paragraph_safe_text(lesson["title"]), styles["title"]))
    subtitle = "" if chinese_only else lesson.get("subtitle", "")
    if subtitle:
        story.append(Paragraph(paragraph_safe_text(subtitle), styles["subtitle"]))
    story.append(Spacer(1, 5 * mm))
    story.append(make_box(labels["usage_title"], Paragraph(labels["usage_text"], styles["body"]), styles, styles["soft"]))
    story.append(Spacer(1, 3 * mm))
    story.append(make_box(labels["coverage_title"], rich_bullet_flowables(lesson["full_review_topics"], styles["body"], chinese_only), styles, styles["card"]))
    story.append(Spacer(1, 3 * mm))
    golden_quotes = build_quote_summary_text(lesson.get("quotes", []), chinese_only)
    if golden_quotes:
        story.append(make_box(labels["quotes_title"], Paragraph(golden_quotes, styles["quote"]), styles, styles["quote_bg"]))
    story.append(PageBreak())

    for index, day in enumerate(days):
        if index > 0:
            story.append(PageBreak())
        story.append(Paragraph(build_day_heading(day, base_date, chinese_only), styles["h1"]))
        if day.get("goal"):
            story.append(Paragraph(f"<b>{labels['goal']}:</b> {localize_paragraph_text(day['goal'], chinese_only)}", styles["body"]))
        if day.get("focus"):
            story.append(Paragraph(f"<b>{labels['focus']}:</b> {localize_paragraph_text(day['focus'], chinese_only)}", styles["body"]))
        if day.get("tasks"):
            story.append(Spacer(1, 2 * mm))
            story.append(make_box(labels["tasks_title"], rich_bullet_flowables(day["tasks"], styles["body"], chinese_only), styles, styles["card"]))
            story.append(Spacer(1, 2 * mm))
        blank_body = rich_numbered_flowables([item[0] for item in day["blanks"]], styles["body"], chinese_only)
        story.append(make_box(labels["blanks_title"], blank_body, styles, styles["card"]))
        story.append(Spacer(1, 2 * mm))
        if day.get("choices"):
            story.append(CondPageBreak(60 * mm))
            story.append(make_box(labels["choices_title"], make_choice_table(day["choices"], styles, chinese_only), styles, styles["paper"]))
        if day.get("method_cards"):
            story.append(Spacer(1, 2 * mm))
            story.append(make_box(
                labels["knowledge_mixed_title"],
                rich_bullet_flowables(day["method_cards"], styles["body"], chinese_only),
                styles,
                styles["paper"],
            ))

        knowledge_items = knowledge_sections.get(day["day"], [])
        has_teacher_quote = index == 0 and day["quotes"]
        has_replay_block = index == 0 and bool(day["quotes"])
        if knowledge_items or has_teacher_quote or has_replay_block:
            story.append(Spacer(1, 2 * mm))
        if knowledge_items:
            knowledge_mode = knowledge_mode_for_day(day, variant_key)
            if knowledge_mode == "mixed":
                knowledge_body = make_knowledge_mixed_table(knowledge_items, styles, chinese_only)
                knowledge_title = labels["knowledge_mixed_title"]
            else:
                knowledge_body = make_knowledge_oral_table(knowledge_items, styles, chinese_only)
                knowledge_title = labels["knowledge_oral_title"]
            story.append(CondPageBreak(70 * mm))
            story.append(make_box(knowledge_title, knowledge_body, styles, styles["paper"]))
            if has_teacher_quote or has_replay_block:
                story.append(Spacer(1, 2 * mm))

        if has_teacher_quote:
            quote_body = Paragraph("<br/>".join([f"“{localize_paragraph_text(quote, chinese_only)}”" for quote in day["quotes"]]), styles["quote"])
            story.append(make_box(labels["teacher_quote_title"], quote_body, styles, styles["quote_bg"]))
            story.append(Spacer(1, 2 * mm))

        if has_replay_block:
            replay_text = build_quote_replay_text(day, labels, chinese_only)
            story.append(make_box(labels["quote_replay_title"], Paragraph(replay_text, styles["body"]), styles, styles["quote_bg"]))
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(labels["check_text"], styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph(labels["final_reminder"], styles["h1"]))
    story.append(make_box(
        labels["final_reminder_box"],
        rich_bullet_flowables(final_reminder_lines, styles["body"], chinese_only),
        styles,
        styles["soft"],
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(labels["answer_key"], styles["h1"]))
    story.append(make_compact_answer_key_table(days, knowledge_sections, styles, labels, variant_key, chinese_only))
    return story


def render_review_plan_pdf(
    *,
    lesson: dict,
    days: list[dict],
    final_reminder_lines: list[str],
    output_path: str,
    variant_key: str = "cn",
    knowledge_sections: dict | None = None,
    style_config: dict[str, Any] | None = None,
    base_date=None,
) -> str:
    register_fonts()
    style_config = style_config or load_unified_review_plan_style_config()
    styles = build_styles(style_config)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=_page_metric(style_config, "left_margin_mm", 18) * mm,
        rightMargin=_page_metric(style_config, "right_margin_mm", 18) * mm,
        topMargin=_page_metric(style_config, "top_margin_mm", 24) * mm,
        bottomMargin=_page_metric(style_config, "bottom_margin_mm", 16) * mm,
        title=lesson["title"],
    )
    canvas_maker = lambda *args, **kwargs: TrackingCanvas(*args, char_space=LETTER_SPACING, **kwargs)
    doc.build(
        build_story(
            styles,
            variant_key,
            lesson=lesson,
            days=days,
            final_reminder_lines=final_reminder_lines,
            knowledge_sections=knowledge_sections or {},
            base_date=base_date or lesson.get("base_date") or lesson.get("date"),
            style_config=style_config,
        ),
        onFirstPage=on_page(styles, variant_key, style_config, lesson["title"]),
        onLaterPages=on_page(styles, variant_key, style_config, lesson["title"]),
        canvasmaker=canvas_maker,
    )
    return str(output.resolve())


def parse_cli_args():
    args = sys.argv[1:]
    variant_key = "cn"
    lesson_pack_path = None

    if args and not args[0].startswith("--"):
        variant_key = args.pop(0)
    if variant_key == "cn_preview":
        variant_key = "cn"
    if variant_key not in VARIANTS:
        valid_keys = ", ".join(sorted(VARIANTS))
        raise SystemExit(f"Unknown variant '{variant_key}'. Valid variants: {valid_keys}")

    while args:
        flag = args.pop(0)
        if flag != "--lesson-pack":
            raise SystemExit(f"Unknown option '{flag}'. Supported option: --lesson-pack <path>")
        if not args:
            raise SystemExit("Missing path after --lesson-pack")
        lesson_pack_path = args.pop(0)

    return variant_key, lesson_pack_path


def main():
    variant_key, lesson_pack_path = parse_cli_args()
    if lesson_pack_path:
        load_lesson_pack(lesson_pack_path)
    OUTPUT_DIR.mkdir(exist_ok=True)
    file_path = build_timestamped_output_path(OUTPUT_DIR, f"{build_lesson_filename_part(LESSON)}.pdf")
    render_review_plan_pdf(
        lesson=LESSON,
        days=DAYS,
        final_reminder_lines=FINAL_REMINDER_LINES,
        output_path=str(file_path),
        variant_key=variant_key,
        knowledge_sections=KNOWLEDGE_SECTIONS,
    )
    print("Created PDFs:")
    print(file_path.name)


if __name__ == "__main__":
    main()
