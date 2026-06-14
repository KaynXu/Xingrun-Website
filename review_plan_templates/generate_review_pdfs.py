from __future__ import annotations

import sys
import re
import importlib.util
import platform
from typing import Any
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import CondPageBreak, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "pdf_output"
OUTPUT_NAME = "review-plan-bilingual-quotes-10-15-quote-replay-layout.pdf"


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

LATEX_BLOCK_DOLLAR_PATTERN = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL)
LATEX_INLINE_PATTERN = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$(?!\$)")
LATEX_PAREN_PATTERN = re.compile(r"\\{1,2}\((.+?)\\{1,2}\)")
LATEX_BRACKET_PATTERN = re.compile(r"\\{1,2}\[(.+?)\\{1,2}\]", re.DOTALL)
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
# Unicode subscript letters that are available (limited set)
SUBSCRIPT_LETTER_MAP = {
    "a": "ₐ", "e": "ₑ", "o": "ₒ", "x": "ₓ", "h": "ₕ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "p": "ₚ",
    "s": "ₛ", "t": "ₜ",
}
SUBSCRIPT_DIGIT_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
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
    result = []
    for c in content:
        if c in SUBSCRIPT_DIGIT_MAP:
            result.append(SUBSCRIPT_DIGIT_MAP[c])
        elif c.lower() in SUBSCRIPT_LETTER_MAP:
            result.append(SUBSCRIPT_LETTER_MAP[c.lower()])
        else:
            # No Unicode subscript available – fall back to _(content) notation
            return f"_({content})"
    return "".join(result)


BROKEN_NEWLINE_LATEX_COMMAND_PATTERN = re.compile(
    r"(?<![。！？.!?：:；;])\n(?=(?:eq\b|otin\b|abla\b|mid\b|parallel\b|subset(?:eq)?\b|supset(?:eq)?\b|rightarrow\b|leftarrow\b|Rightarrow\b|Leftarrow\b|iff\b))"
)


def _repair_latex_transport_controls(text: str) -> str:
    repaired = str(text or "").replace("\r\n", "\n")
    repaired = repaired.replace("\t", "\\t")
    repaired = repaired.replace("\f", "\\f")
    repaired = repaired.replace("\b", "\\b")
    repaired = repaired.replace("\r", "\\r")
    return BROKEN_NEWLINE_LATEX_COMMAND_PATTERN.sub(r"\\n", repaired)


def _normalize_bare_latex_text(text: str) -> str:
    normalized = str(text or "").replace(r"\$", "$")

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
    normalized = _repair_latex_transport_controls(text).replace("\\\\", "\\")
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
    normalized = re.sub(r"\s{2,}", " ", normalized)
    normalized = re.sub(r"(^|\s)-\s*", r"\1- ", normalized)
    normalized = normalized.replace("XRRIGHTARROWTOKEN", "→")
    normalized = normalized.replace("XRLEFTARROWTOKEN", "←")
    return normalized.strip()


def localize_text(value, chinese_only):
    if not isinstance(value, str):
        return value

    if not chinese_only:
        return normalize_portable_text(value)

    localized = value.split(" / ", 1)[0].strip()
    localized = re.sub(r"([。！？：；）】』”])\s*[A-Za-z][\s\S]*$", r"\1", localized)
    return normalize_portable_text(localized.strip())


def localize_lines(values, chinese_only):
    return [localize_text(value, chinese_only) for value in values]


def build_labels(chinese_only):
    if chinese_only:
        return {
            "date": "日期",
            "version": "版本",
            "quote_ratio": "原话比例",
            "layout": "页面风格",
            "day_zero": "第0天",
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
            "footer_right": "课堂原话回放 | 第{page}页",
        }

    return {
        "date": "Date",
        "version": "版本 / Version",
        "quote_ratio": "原话比例 / Quote Ratio",
        "layout": "页面风格 / Layout",
        "day_zero": "第0天 / Day 0",
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
        "footer_right": "Quote Replay Layout | Page {page}",
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
        f"{index}. {escape(localize_text(quote, chinese_only))}"
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
        f"{index}. “{escape(localize_text(quote, chinese_only))}”"
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


def build_day_heading(day, base_date, chinese_only=False):
    review_date = base_date + timedelta(days=day["offset"])
    day_label = localize_text(day["day"], chinese_only)
    if chinese_only:
        return f"{day_label}  |  日期：{format_iso_date(review_date)}"
    return f"{day_label}  |  Date: {format_iso_date(review_date)}"


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
    accent = _palette_color(style_config, "accent", "#8A4B08")
    soft = _palette_color(style_config, "soft", "#FFF3E6")
    quote_bg = _palette_color(style_config, "quote_bg", "#FFF8F0")
    return {
        "accent": accent,
        "soft": soft,
        "quote_bg": quote_bg,
        "title": ParagraphStyle("title", parent=base, fontSize=20, leading=26, alignment=TA_CENTER, textColor=accent),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=11, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#666666")),
        "h1": ParagraphStyle("h1", parent=base, fontSize=14.5, leading=20, textColor=accent, spaceBefore=6, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base, fontSize=12, leading=17, textColor=accent, spaceBefore=3, spaceAfter=3),
        "body": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8.6, leading=12),
        "tiny": ParagraphStyle("tiny", parent=base, fontSize=6.7, leading=8.0),
        "quote": ParagraphStyle("quote", parent=base, fontSize=10, leading=15, leftIndent=6, rightIndent=6),
    }


def bullet_paragraph(items, style):
    return Paragraph("<br/>".join([f"- {item}" for item in items]), style)


def make_box(title, body, styles, background):
    box = Table([[Paragraph(f"<b>{title}</b>", styles["h2"])], [body]], colWidths=[170 * mm])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.8, styles["accent"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return box


def make_choice_table(choices, styles, chinese_only=False):
    rows = []
    for index, choice in enumerate(choices, start=1):
        rows.append(
            [
                Paragraph(f"{index}. {localize_text(choice['question'], chinese_only)}", styles["body"]),
                Paragraph("<br/>".join(localize_lines(choice["options"], chinese_only)), styles["small"]),
            ]
        )
    table = Table(rows, colWidths=[80 * mm, 78 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, styles["accent"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D2D8DE")),
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
        rows.append([Paragraph(f"{labels['blank_prefix']} {index}", styles["small"]), Paragraph(item[1], styles["small"])])
    for index, item in enumerate(day["choices"], start=1):
        rows.append([Paragraph(f"{labels['choice_prefix']} {index}", styles["small"]), Paragraph(item["answer"], styles["small"])])
    table = Table(rows, colWidths=[34 * mm, 136 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8EFE7")),
                ("BOX", (0, 0), (-1, -1), 0.6, styles["accent"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D2D8DE")),
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
        parts = [f"<b>{localize_text(item['title'], chinese_only)}</b>"]
        for index, blank in enumerate(item["mixed"]["blanks"], start=1):
            parts.append(f"填空 {index}. {localize_text(blank[0], chinese_only)}")
        for index, choice in enumerate(item["mixed"]["choices"], start=1):
            option_text = "<br/>".join(localize_lines(choice["options"], chinese_only))
            parts.append(f"选择 {index}. {localize_text(choice['question'], chinese_only)}<br/>{option_text}")
        rows.append([Paragraph("<br/><br/>".join(parts), styles["body"])])
    table = Table(rows, colWidths=[158 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, styles["accent"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D2D8DE")),
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
        prompt_lines = [f"<b>{localize_text(item['title'], chinese_only)}</b>"]
        for index, prompt in enumerate(item["oral"]["prompts"], start=1):
            prompt_lines.append(f"提问 {index}. {localize_text(prompt, chinese_only)}")
        rows.append([Paragraph("<br/><br/>".join(prompt_lines), styles["body"])])
    table = Table(rows, colWidths=[158 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, styles["accent"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D2D8DE")),
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
                rows.append([Paragraph(f"{title} {labels['blank_prefix']} {index}", styles["small"]), Paragraph(blank[1], styles["small"])])
            for index, choice in enumerate(item["mixed"]["choices"], start=1):
                rows.append([Paragraph(f"{title} {labels['choice_prefix']} {index}", styles["small"]), Paragraph(choice["answer"], styles["small"])])
        else:
            for index, keypoint in enumerate(item["oral"]["keypoints"], start=1):
                rows.append([Paragraph(f"{title} {labels['oral_prompt_prefix']} {index}", styles["small"]), Paragraph(localize_text(keypoint, chinese_only), styles["small"])])
    table = Table(rows, colWidths=[50 * mm, 120 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8EFE7")),
                ("BOX", (0, 0), (-1, -1), 0.6, styles["accent"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D2D8DE")),
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
            entries.append((day_label, f"{labels['blank_prefix']} {index}", escape(normalize_portable_text(item[1]))))
        for index, item in enumerate(day["choices"], start=1):
            entries.append((day_label, f"{labels['choice_prefix']} {index}", escape(normalize_portable_text(item["answer"]))))

        knowledge_items = knowledge_sections.get(day["day"], [])
        if not knowledge_items:
            continue
        knowledge_mode = knowledge_mode_for_day(day, variant_key)
        for item in knowledge_items:
            title = localize_text(item["title"], chinese_only)
            if knowledge_mode == "mixed":
                for index, blank in enumerate(item["mixed"]["blanks"], start=1):
                    entries.append((day_label, escape(f"{title} {labels['blank_prefix']} {index}"), escape(normalize_portable_text(blank[1]))))
                for index, choice in enumerate(item["mixed"]["choices"], start=1):
                    entries.append((day_label, escape(f"{title} {labels['choice_prefix']} {index}"), escape(normalize_portable_text(choice["answer"]))))
            else:
                for index, keypoint in enumerate(item["oral"]["keypoints"], start=1):
                    entries.append((day_label, escape(f"{title} {labels['oral_prompt_prefix']} {index}"), escape(localize_text(keypoint, chinese_only))))

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
            Paragraph(left_entry[0], styles["tiny"]),
            Paragraph(left_entry[1], styles["tiny"]),
            Paragraph(left_entry[2], styles["tiny"]),
            Paragraph(right_entry[0], styles["tiny"]),
            Paragraph(right_entry[1], styles["tiny"]),
            Paragraph(right_entry[2], styles["tiny"]),
        ])

    table = Table(rows, colWidths=[15 * mm, 33 * mm, 37 * mm, 15 * mm, 33 * mm, 37 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8EFE7")),
                ("BOX", (0, 0), (-1, -1), 0.6, styles["accent"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D2D8DE")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return table


def on_page(styles, variant_key, lesson_title=None):
    chinese_only = is_chinese_only(variant_key)
    labels = build_labels(chinese_only)
    footer_title = lesson_title or LESSON["title"]

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(styles["accent"])
        canvas.setLineWidth(1)
        canvas.line(doc.leftMargin, A4[1] - 18 * mm, A4[0] - doc.rightMargin, A4[1] - 18 * mm)
        canvas.setFont(ACTIVE_FONT_NAME, 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(doc.leftMargin, 10 * mm, footer_title)
        canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, labels["footer_right"].format(page=canvas.getPageNumber()))
        canvas.restoreState()

    return draw


def build_story(styles, variant_key, *, lesson=None, days=None, final_reminder_lines=None, knowledge_sections=None, base_date=None):
    base_date = _coerce_base_date(base_date)
    chinese_only = is_chinese_only(variant_key)
    labels = build_labels(chinese_only)
    lesson = lesson or LESSON
    days = days or DAYS
    final_reminder_lines = final_reminder_lines or FINAL_REMINDER_LINES
    knowledge_sections = knowledge_sections if knowledge_sections is not None else KNOWLEDGE_SECTIONS
    story = []
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(lesson["title"], styles["title"]))
    subtitle = "" if chinese_only else lesson.get("subtitle", "")
    if subtitle:
        story.append(Paragraph(subtitle, styles["subtitle"]))
    story.append(Spacer(1, 5 * mm))
    story.append(make_box(labels["usage_title"], Paragraph(labels["usage_text"], styles["body"]), styles, styles["soft"]))
    story.append(Spacer(1, 3 * mm))
    story.append(make_box(labels["coverage_title"], bullet_paragraph(localize_lines(lesson["full_review_topics"], chinese_only), styles["body"]), styles, colors.white))
    story.append(Spacer(1, 3 * mm))
    golden_quotes = build_quote_summary_text(lesson.get("quotes", []), chinese_only)
    story.append(make_box(labels["quotes_title"], Paragraph(golden_quotes, styles["quote"]), styles, styles["quote_bg"]))
    story.append(PageBreak())

    for index, day in enumerate(days):
        if index > 0:
            story.append(PageBreak())
        story.append(Paragraph(build_day_heading(day, base_date, chinese_only), styles["h1"]))
        if index == 0:
            story.append(Paragraph(f"<b>{labels['goal']}:</b> {localize_text(day['goal'], chinese_only)}", styles["body"]))
            story.append(Paragraph(f"<b>{labels['focus']}:</b> {localize_text(day['focus'], chinese_only)}", styles["body"]))
            story.append(Spacer(1, 2 * mm))
            story.append(make_box(labels["coverage_title"], bullet_paragraph(localize_lines(lesson["full_review_topics"], chinese_only), styles["body"]), styles, styles["soft"]))
            story.append(Spacer(1, 2 * mm))
            story.append(make_box(labels["tasks_title"], bullet_paragraph(localize_lines(day["tasks"], chinese_only), styles["body"]), styles, colors.white))
            story.append(Spacer(1, 2 * mm))
        blank_body = Paragraph("<br/>".join([f"{index}. {localize_text(item[0], chinese_only)}" for index, item in enumerate(day["blanks"], start=1)]), styles["body"])
        story.append(make_box(labels["blanks_title"], blank_body, styles, colors.white))
        story.append(Spacer(1, 2 * mm))
        story.append(CondPageBreak(60 * mm))
        story.append(make_box(labels["choices_title"], make_choice_table(day["choices"], styles, chinese_only), styles, colors.white))
        story.append(Spacer(1, 2 * mm))

        knowledge_items = knowledge_sections.get(day["day"], [])
        if knowledge_items:
            knowledge_mode = knowledge_mode_for_day(day, variant_key)
            if knowledge_mode == "mixed":
                knowledge_body = make_knowledge_mixed_table(knowledge_items, styles, chinese_only)
                knowledge_title = labels["knowledge_mixed_title"]
            else:
                knowledge_body = make_knowledge_oral_table(knowledge_items, styles, chinese_only)
                knowledge_title = labels["knowledge_oral_title"]
            story.append(CondPageBreak(70 * mm))
            story.append(make_box(knowledge_title, knowledge_body, styles, colors.white))
            story.append(Spacer(1, 2 * mm))

        if index == 0 and day["quotes"]:
            quote_body = Paragraph("<br/>".join([f"“{quote}”" for quote in day["quotes"]]), styles["quote"])
            story.append(make_box(labels["teacher_quote_title"], quote_body, styles, styles["quote_bg"]))
            story.append(Spacer(1, 2 * mm))

        if index == 0:
            replay_text = build_quote_replay_text(day, labels, chinese_only)
            story.append(make_box(labels["quote_replay_title"], Paragraph(replay_text, styles["body"]), styles, styles["quote_bg"]))
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(labels["check_text"], styles["body"]))
            story.append(Spacer(1, 3 * mm))

    story.append(PageBreak())
    story.append(Paragraph(labels["final_reminder"], styles["h1"]))
    story.append(make_box(
        labels["final_reminder_box"],
        bullet_paragraph(
            localize_lines(final_reminder_lines, chinese_only),
            styles["body"],
        ),
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
    styles = build_styles(style_config)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=24 * mm,
        bottomMargin=16 * mm,
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
        ),
        onFirstPage=on_page(styles, variant_key, lesson["title"]),
        onLaterPages=on_page(styles, variant_key, lesson["title"]),
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
