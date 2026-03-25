#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成学生复习计划填空题讲义 PDF
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# ── 注册中文字体 ──────────────────────────────────────────────
pdfmetrics.registerFont(TTFont('STHeiti', '/System/Library/Fonts/STHeiti Medium.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('STHeitiLight', '/System/Library/Fonts/STHeiti Light.ttc', subfontIndex=0))

FONT_MAIN  = 'STHeiti'
FONT_LIGHT = 'STHeitiLight'

# ── 颜色 ──────────────────────────────────────────────────────
C_HEADER   = colors.HexColor('#1a3a5c')   # 深蓝
C_DAY1     = colors.HexColor('#2e6da4')   # 中蓝（第1天）
C_DAILY    = colors.HexColor('#3a7d44')   # 绿（每日）
C_LIGHT_BG = colors.HexColor('#f0f5fb')   # 浅蓝背景
C_GREEN_BG = colors.HexColor('#f0faf2')   # 浅绿背景
C_BORDER   = colors.HexColor('#b0c8e8')
C_LINE     = colors.HexColor('#999999')
C_WARN     = colors.HexColor('#c0392b')   # 红色提示

BLANK = '＿＿＿＿＿'
BLANK_S = '＿＿＿'

# ── 样式 ──────────────────────────────────────────────────────
def make_styles():
    base = dict(fontName=FONT_MAIN, leading=20)
    return {
        'title': ParagraphStyle('title', fontName=FONT_MAIN, fontSize=18,
                                leading=28, textColor=C_HEADER, spaceAfter=4,
                                alignment=1),
        'subtitle': ParagraphStyle('subtitle', fontName=FONT_LIGHT, fontSize=11,
                                   leading=18, textColor=colors.HexColor('#555555'),
                                   alignment=1, spaceAfter=12),
        'day_title': ParagraphStyle('day_title', fontName=FONT_MAIN, fontSize=13,
                                    leading=22, textColor=colors.white, spaceAfter=0),
        'section': ParagraphStyle('section', fontName=FONT_MAIN, fontSize=11,
                                  leading=20, textColor=C_HEADER, spaceBefore=6,
                                  spaceAfter=2),
        'body': ParagraphStyle('body', fontName=FONT_LIGHT, fontSize=10.5,
                               leading=20, textColor=colors.HexColor('#222222'),
                               leftIndent=8, spaceAfter=2),
        'blank_line': ParagraphStyle('blank_line', fontName=FONT_LIGHT, fontSize=10.5,
                                     leading=22, textColor=colors.HexColor('#222222'),
                                     leftIndent=16, spaceAfter=1),
        'self_test': ParagraphStyle('self_test', fontName=FONT_MAIN, fontSize=10,
                                    leading=19, textColor=C_WARN,
                                    leftIndent=8, spaceAfter=2),
        'tip': ParagraphStyle('tip', fontName=FONT_LIGHT, fontSize=9.5,
                              leading=17, textColor=colors.HexColor('#666666'),
                              leftIndent=8, spaceBefore=2, spaceAfter=4),
        'week_title': ParagraphStyle('week_title', fontName=FONT_MAIN, fontSize=12,
                                     leading=22, textColor=colors.white),
        'week_body': ParagraphStyle('week_body', fontName=FONT_LIGHT, fontSize=10,
                                    leading=19, textColor=colors.HexColor('#333333'),
                                    leftIndent=12, spaceAfter=2),
    }

S = make_styles()

PAGE_W, PAGE_H = A4
LM = RM = 1.8 * cm
CONTENT_W = PAGE_W - LM - RM


# ── 辅助：带彩色背景的标题栏 ──────────────────────────────────
def day_header(label, time_note, color):
    text = f"{label}　　<font size='9'>{time_note}</font>"
    p = Paragraph(text, S['day_title'])
    tbl = Table([[p]], colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), color),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    return tbl


def section_box(items, bg_color, border_color):
    """将多个 Paragraph 放入一个有背景色的框"""
    rows = [[item] for item in items]
    tbl = Table(rows, colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), bg_color),
        ('BOX',           (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]))
    return tbl


def write_line(text):
    return Paragraph(text, S['blank_line'])

def body(text):
    return Paragraph(text, S['body'])

def section(text):
    return Paragraph(text, S['section'])

def self_test(text):
    return Paragraph(text, S['self_test'])

def tip(text):
    return Paragraph(text, S['tip'])

def spacer(h=0.2):
    return Spacer(1, h * cm)


# ── 页面内容构建 ──────────────────────────────────────────────
def build_story():
    story = []

    # ── 封面标题 ──
    story.append(spacer(0.5))
    story.append(Paragraph('初中数学　复习计划讲义', S['title']))
    story.append(Paragraph('学生填写版　·　每天5分钟以内　·　课后8天跟踪复习', S['subtitle']))
    story.append(HRFlowable(width=CONTENT_W, thickness=1.5, color=C_HEADER, spaceAfter=10))

    # ────────────────────────────────────────────────────────────
    # 第1天
    # ────────────────────────────────────────────────────────────
    story.append(KeepTogether([
        day_header('📘  学后第1天复习', '（总计 4–5 分钟）', C_DAY1),
        spacer(0.15),
    ]))

    # 第1步
    story.append(section('⏱ 第1步（1分钟）：口头回忆四大板块'))
    items = [
        body('这节课主要学了哪四块内容？'),
        write_line(f'① 审题与计算　② {BLANK}　③ {BLANK}　④ {BLANK}'),
    ]
    story.append(section_box(items, C_LIGHT_BG, C_BORDER))
    story.append(spacer(0.2))

    # 第2步
    story.append(section('⏱ 第2步（2分钟）：翻笔记，看4条关键提醒'))
    items = [
        write_line(f'① 计算不能 {BLANK_S} 步'),
        write_line(f'② 读题不能用 {BLANK_S}　（一目十行地泛读）'),
        write_line(f'③ 分式方程：求解之前先确认 {BLANK} 不为零'),
        write_line(f'④ 几何题：看到 {BLANK_S} 或 45°，要主动联想解题模型'),
    ]
    story.append(section_box(items, C_LIGHT_BG, C_BORDER))
    story.append(spacer(0.2))

    # 第3步
    story.append(section('⏱ 第3步（1–2分钟）：4道口头自测'))
    items = [
        write_line(f'Q1：4 − m²  正确分解为 ＿＿＿＿＿＿＿＿＿＿'),
        write_line(f'Q2：含参二次方程，解题前必须先讨论 {BLANK}'),
        write_line(f'Q3：分式方程求完解之后，还必须 {BLANK_S} ，原因是 {BLANK}'),
        write_line(f'Q4：几何题看到中点，优先想 {BLANK} 和 {BLANK}'),
    ]
    story.append(section_box(items, C_LIGHT_BG, C_BORDER))
    story.append(spacer(0.3))

    # ────────────────────────────────────────────────────────────
    # 第2天
    # ────────────────────────────────────────────────────────────
    story.append(KeepTogether([
        day_header('✏️  第2天　每日一练前复习', '（3 分钟）　主题：审题 ＋ 计算规范', C_DAILY),
        spacer(0.15),
    ]))
    items = [
        body('📌 今天做题前先背这3步：'),
        write_line(f'① 逐字读题 → 用笔 {BLANK_S} 条件 → 用笔 {BLANK_S} 问题'),
        write_line(f'② 分式计算：每一步都要 {BLANK_S} ，不能跳步'),
        write_line(f'③ 因式分解：4 − m² ≠ ({BLANK_S} − m)²，正确是 ({BLANK_S})({BLANK_S})'),
        body(''),
        self_test(f'💬 出发口令：「我今天做题前先 {BLANK_S} 条件，计算题一步一步写清楚。」'),
    ]
    story.append(section_box(items, C_GREEN_BG, colors.HexColor('#a8d5b5')))
    story.append(spacer(0.3))

    # ────────────────────────────────────────────────────────────
    # 第3天
    # ────────────────────────────────────────────────────────────
    story.append(KeepTogether([
        day_header('✏️  第3天　每日一练前复习', '（4 分钟）　主题：因式分解 ＋ 一元二次方程', C_DAILY),
        spacer(0.15),
    ]))
    items = [
        body('📌 翻笔记，只看这几条：'),
        write_line(f'① 平方 {BLANK_S} 公式：a² − b² ＝ {BLANK}'),
        write_line(f'② 提 {BLANK_S} 因式：先看每一项有没有公共因子'),
        write_line(f'③ 判别式 Δ ＝ {BLANK}　有实根 ↔ Δ {BLANK} 0'),
        write_line(f'④ 含参二次方程：解题前必须分两种情况讨论 {BLANK}'),
        body(''),
        self_test(f'💬 出发口令：「含参二次方程，先看 {BLANK_S} 是不是二次方程（二次项系数是否为零）。」'),
    ]
    story.append(section_box(items, C_GREEN_BG, colors.HexColor('#a8d5b5')))
    story.append(spacer(0.3))

    # ────────────────────────────────────────────────────────────
    # 第4天
    # ────────────────────────────────────────────────────────────
    story.append(KeepTogether([
        day_header('✏️  第4天　每日一练前复习', '（4 分钟）　主题：韦达定理 ＋ 分式方程', C_DAILY),
        spacer(0.15),
    ]))
    items = [
        body('📌 翻笔记，只看这几条：'),
        write_line(f'① 韦达定理：对于 ax²＋bx＋c＝0，两根之和 ＝ {BLANK}，两根之积 ＝ {BLANK}'),
        write_line(f'② 分式方程解完后必须 {BLANK_S} 原方程，检查分母是否等于 {BLANK_S}'),
        write_line(f'③ 做题：先由已知条件列 {BLANK} 式，再代入韦达定理'),
        body(''),
        self_test(f'💬 出发口令：「分式方程最后一定 {BLANK_S} 分母，韦达定理先确认对应 {BLANK_S}。」'),
    ]
    story.append(section_box(items, C_GREEN_BG, colors.HexColor('#a8d5b5')))
    story.append(spacer(0.3))

    # ────────────────────────────────────────────────────────────
    # 第5天
    # ────────────────────────────────────────────────────────────
    story.append(KeepTogether([
        day_header('✏️  第5天　每日一练前复习', '（4–5 分钟）　主题：应用题四步法', C_DAILY),
        spacer(0.15),
    ]))
    items = [
        body('📌 应用题标准四步，在草稿纸上写出框架再做：'),
        write_line(f'第一步：列 {BLANK} 方程 → 求出单件 {BLANK}'),
        write_line(f'第二步：设购进 x 件，列 {BLANK} 组 → 确定 x 的范围'),
        write_line(f'第三步：写出 {BLANK} 函数 W（W 与 x 的关系），判断增减性 → 求最大 {BLANK}'),
        write_line(f'第四步：剩余金额列 {BLANK} 方程，求整数解'),
        body(''),
        self_test(f'💬 出发口令：「应用题不要一口气做到底，先求 {BLANK_S}，再定 {BLANK_S}，再求最大 {BLANK_S}。」'),
    ]
    story.append(section_box(items, C_GREEN_BG, colors.HexColor('#a8d5b5')))
    story.append(spacer(0.3))

    # ────────────────────────────────────────────────────────────
    # 第6天
    # ────────────────────────────────────────────────────────────
    story.append(KeepTogether([
        day_header('✏️  第6天　每日一练前复习', '（4 分钟）　主题：几何基础模型', C_DAILY),
        spacer(0.15),
    ]))
    items = [
        body('📌 三个基础模型，回忆完整定义：'),
        write_line(f'① 中位线：连接两边 {BLANK_S} 点的线段，平行于 {BLANK_S}，且等于它的 {BLANK_S}'),
        write_line(f'② 平行＋角平分 → 构造 {BLANK_S} 三角形，得 {BLANK} ＝ {BLANK}'),
        write_line(f'③ 倍长 {BLANK_S} 线：专用场景是题目给出了 {BLANK_S}，目的是构造 {BLANK_S} 三角形'),
        body(''),
        self_test(f'💬 出发口令：「看到中点，先想 {BLANK_S} 和倍长中线；看到平行加角平分，先想 {BLANK_S}。」'),
    ]
    story.append(section_box(items, C_GREEN_BG, colors.HexColor('#a8d5b5')))
    story.append(spacer(0.3))

    # ────────────────────────────────────────────────────────────
    # 第7天
    # ────────────────────────────────────────────────────────────
    story.append(KeepTogether([
        day_header('✏️  第7天　每日一练前复习', '（4 分钟）　主题：特殊角 ＋ 辅助线', C_DAILY),
        spacer(0.15),
    ]))
    items = [
        body('📌 看到这些条件，第一时间想到什么？'),
        write_line(f'① 题目出现 45°  → 联想 {BLANK_S} 法（手拉手模型），把 △ 绕顶点旋转 {BLANK_S}°'),
        write_line(f'② 需要求某条线段长 → 优先考虑作 {BLANK_S} 线，配合 {BLANK_S} 三角形'),
        write_line(f'③ 想连接两个图形的元素 → 作 {BLANK_S} 线，利用平行性质'),
        write_line(f'④ 三角函数配合：∠=45° → sin45°＝ {BLANK_S}，cos45°＝ {BLANK_S}'),
        body(''),
        self_test(f'💬 出发口令：「看到45°，先想 {BLANK_S}；要求长度，先想 {BLANK_S} 和直角三角形。」'),
    ]
    story.append(section_box(items, C_GREEN_BG, colors.HexColor('#a8d5b5')))
    story.append(spacer(0.3))

    # ────────────────────────────────────────────────────────────
    # 第8天
    # ────────────────────────────────────────────────────────────
    story.append(KeepTogether([
        day_header('✏️  第8天　每日一练前复习', '（4 分钟）　主题：圆·翻折·相似·坐标综合', C_DAILY),
        spacer(0.15),
    ]))
    items = [
        body('📌 综合板块，每条都补全：'),
        write_line(f'① 四点共圆的判定：对角之和 ＝ {BLANK_S}°，或同弧所对圆周角 {BLANK_S}'),
        write_line(f'② 翻折（折叠）：折叠前后图形 {BLANK_S}，对应边、对应角分别 {BLANK_S}'),
        write_line(f'③ 相似三角形：先找 {BLANK_S}，找到两组对应角相等即可证相似'),
        write_line(f'④ 将军饮马：对 {BLANK_S} 做 {BLANK_S} 对称，把折线变成两点间 {BLANK_S}'),
        write_line(f'⑤ 存在性问题：必须 {BLANK_S} 讨论（以不同点为直角顶点），不能漏情况'),
        body(''),
        self_test(f'💬 出发口令：「圆看 {BLANK_S} 互补，相似先找 {BLANK_S}，存在性一定 {BLANK_S}。」'),
    ]
    story.append(section_box(items, C_GREEN_BG, colors.HexColor('#a8d5b5')))
    story.append(spacer(0.4))

    # ────────────────────────────────────────────────────────────
    # 周复盘
    # ────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=CONTENT_W, thickness=1, color=colors.HexColor('#cccccc'), spaceAfter=8))
    hdr = Paragraph('🗓  周复盘（每周结束后填写）', S['week_title'])
    hdr_tbl = Table([[hdr]], colWidths=[CONTENT_W])
    hdr_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_HEADER),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
    ]))
    story.append(hdr_tbl)
    story.append(spacer(0.15))

    week_items = [
        write_line(f'1. 这周哪个知识点最容易忘？  → {BLANK * 2}'),
        write_line(f'2. 哪天的复习最有效？原因是  → {BLANK * 2}'),
        write_line(f'3. 下周做题前要额外注意：    → {BLANK * 2}'),
        write_line(f'4. 我需要老师再讲一遍的是：  → {BLANK * 2}'),
    ]
    story.append(section_box(week_items, C_LIGHT_BG, C_BORDER))
    story.append(spacer(0.3))

    # 底部说明
    story.append(tip('★ 执行方法：每天练前 闭眼30秒回忆主题 → 翻笔记1分钟 → 说出1条提醒 → 口头自测1–2分钟'))
    story.append(tip('★ 本讲义由老师课后生成，每节新课后更新。填完的页面请保存，期末可一起回顾。'))

    return story


# ── 主函数 ────────────────────────────────────────────────────
def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, 'student_review_plan_fill_blanks.pdf')

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=LM,
        rightMargin=RM,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title='初中数学复习计划讲义（学生填写版）',
        author='课后自动生成',
    )
    story = build_story()
    doc.build(story)
    print(f'PDF 已生成：{out_path}')


if __name__ == '__main__':
    main()
