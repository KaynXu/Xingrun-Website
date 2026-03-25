#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 生成引擎（数据驱动版）
可生成：
  - 单节课 8 天复习讲义（学生填写版）
  - 月度综合复习讲义
"""

import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ─── 字体注册（跨平台）────────────────────────────────────────────────────────────
_FONT_REGISTERED = False
FONT_MAIN  = 'CJKMain'
FONT_LIGHT = 'CJKLight'


def _find_cjk_fonts():
    """
    返回 (main_path, light_path)。
    按 macOS → Windows → Linux 顺序尝试。
    """
    import platform
    plat = platform.system()

    candidates = []
    if plat == 'Darwin':
        candidates = [
            ('/System/Library/Fonts/STHeiti Medium.ttc',
             '/System/Library/Fonts/STHeiti Light.ttc'),
            ('/Library/Fonts/Arial Unicode.ttf',
             '/Library/Fonts/Arial Unicode.ttf'),
        ]
    elif plat == 'Windows':
        candidates = [
            ('C:/Windows/Fonts/msyh.ttc',  'C:/Windows/Fonts/msyhl.ttc'),
            ('C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/simhei.ttf'),
            ('C:/Windows/Fonts/simsun.ttc', 'C:/Windows/Fonts/simsun.ttc'),
        ]
    else:  # Linux
        candidates = [
            ('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
             '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'),
            ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
             '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
            ('/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
             '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc'),
        ]

    for main, light in candidates:
        if Path(main).exists():
            return main, light if Path(light).exists() else main

    return None, None


def _ensure_fonts():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    main_path, light_path = _find_cjk_fonts()
    if main_path:
        try:
            pdfmetrics.registerFont(TTFont('CJKMain', main_path, subfontIndex=0))
        except Exception:
            pdfmetrics.registerFont(TTFont('CJKMain', main_path))
        try:
            pdfmetrics.registerFont(TTFont('CJKLight', light_path, subfontIndex=0))
        except Exception:
            pdfmetrics.registerFont(TTFont('CJKLight', light_path))
    else:
        # 最后备用：用 Helvetica（中文会乱码，但不崩溃）
        from reportlab.lib.fonts import addMapping
        pdfmetrics.registerFont(TTFont.__new__(TTFont))
        import warnings
        warnings.warn("未找到中文字体，PDF 中文字符可能显示为方块。"
                      "请安装 WQY MicroHei 或 Microsoft YaHei。")
    _FONT_REGISTERED = True

# ─── 颜色 ──────────────────────────────────────────────────────────────────────
C_HEADER   = colors.HexColor('#1a3a5c')
C_DAY1     = colors.HexColor('#2e6da4')
C_DAILY    = colors.HexColor('#3a7d44')
C_MONTH    = colors.HexColor('#7b4fa8')   # 紫色（月度复习）
C_LIGHT_BG = colors.HexColor('#f0f5fb')
C_GREEN_BG = colors.HexColor('#f0faf2')
C_PURPLE_BG= colors.HexColor('#f5f0fb')
C_BORDER   = colors.HexColor('#b0c8e8')
C_GREEN_BD = colors.HexColor('#a8d5b5')
C_PURPLE_BD= colors.HexColor('#c4a8e0')
C_WARN     = colors.HexColor('#c0392b')
C_GREY     = colors.HexColor('#666666')

BLANK      = '＿＿＿＿＿'  # 标准空格（5个全角下划线）

PAGE_W, PAGE_H = A4
LM = RM = 1.8 * cm
CONTENT_W = PAGE_W - LM - RM


# ─── 样式工厂 ──────────────────────────────────────────────────────────────────
def _make_styles():
    return {
        'title': ParagraphStyle('title', fontName=FONT_MAIN, fontSize=18,
                                leading=28, textColor=C_HEADER, spaceAfter=4, alignment=1),
        'subtitle': ParagraphStyle('subtitle', fontName=FONT_LIGHT, fontSize=10.5,
                                   leading=18, textColor=C_GREY, alignment=1, spaceAfter=10),
        'meta': ParagraphStyle('meta', fontName=FONT_LIGHT, fontSize=9.5,
                               leading=16, textColor=C_GREY, alignment=1, spaceAfter=8),
        'day_title': ParagraphStyle('day_title', fontName=FONT_MAIN, fontSize=12.5,
                                    leading=22, textColor=colors.white),
        'section': ParagraphStyle('section', fontName=FONT_MAIN, fontSize=10.5,
                                  leading=20, textColor=C_HEADER, spaceBefore=5, spaceAfter=2),
        'body': ParagraphStyle('body', fontName=FONT_LIGHT, fontSize=10,
                               leading=19, textColor=colors.HexColor('#222222'),
                               leftIndent=8, spaceAfter=2),
        'fill': ParagraphStyle('fill', fontName=FONT_LIGHT, fontSize=10,
                               leading=21, textColor=colors.HexColor('#222222'),
                               leftIndent=16, spaceAfter=1),
        'self_test': ParagraphStyle('self_test', fontName=FONT_MAIN, fontSize=10,
                                    leading=19, textColor=C_WARN, leftIndent=8, spaceAfter=2),
        'tip': ParagraphStyle('tip', fontName=FONT_LIGHT, fontSize=9,
                              leading=16, textColor=C_GREY, leftIndent=8, spaceBefore=2, spaceAfter=4),
        'q_q': ParagraphStyle('q_q', fontName=FONT_LIGHT, fontSize=10,
                              leading=19, textColor=colors.HexColor('#222222'), leftIndent=8),
        'q_a': ParagraphStyle('q_a', fontName=FONT_LIGHT, fontSize=9.5,
                              leading=17, textColor=C_GREY, leftIndent=20, spaceAfter=3),
    }


# ─── 低级渲染助手 ───────────────────────────────────────────────────────────────
def _normalize_blanks(text: str) -> str:
    """将 ____ 替换为全角下划线，保证渲染统一"""
    return text.replace('____', BLANK)


def _day_header(label: str, time_note: str, color, styles: dict):
    text = f"{label}　　<font size='9'>{time_note}</font>"
    p = Paragraph(text, styles['day_title'])
    tbl = Table([[p]], colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), color),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
    ]))
    return tbl


def _box(item_paragraphs: list, bg: colors.Color, border: colors.Color):
    rows = [[p] for p in item_paragraphs]
    tbl = Table(rows, colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), bg),
        ('BOX',           (0, 0), (-1, -1), 0.5, border),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _spacer(h=0.2):
    return Spacer(1, h * cm)


def _render_item(item: dict, styles: dict) -> Paragraph:
    text = _normalize_blanks(item.get("text", ""))
    t = item.get("type", "body")
    if t == "fill":
        return Paragraph(text, styles['fill'])
    elif t == "self_test":
        return Paragraph(text, styles['self_test'])
    else:
        return Paragraph(text, styles['body'])


# ─── Day 1 渲染（step 结构）──────────────────────────────────────────────────
def _render_day1(day_data: dict, styles: dict, bg: colors.Color,
                 border: colors.Color) -> list:
    elements = [
        KeepTogether([
            _day_header(day_data["label"], day_data.get("time", ""), C_DAY1, styles),
            _spacer(0.15),
        ])
    ]
    steps = day_data.get("steps", [])
    for step in steps:
        elements.append(Paragraph(
            f"{step.get('step_label','')}：<b>{step.get('title','')}</b>",
            styles['section']
        ))
        paras = [_render_item(it, styles) for it in step.get("items", [])]
        elements.append(_box(paras, bg, border))
        elements.append(_spacer(0.2))

    phrase = day_data.get("self_test_phrase", "")
    if phrase:
        elements.append(_box(
            [Paragraph(_normalize_blanks(phrase), styles['self_test'])],
            colors.HexColor('#fff6f6'), colors.HexColor('#f5c6c6')
        ))
    elements.append(_spacer(0.3))
    return elements


# ─── Daily 渲染（扁平 items）────────────────────────────────────────────────
def _render_daily(day_data: dict, styles: dict, bg: colors.Color,
                  border: colors.Color, header_color: colors.Color) -> list:
    theme = day_data.get("theme", "")
    label = day_data["label"]
    time_note = day_data.get("time", "")
    if theme:
        time_note = f"{time_note}　主题：{theme}"

    elements = [
        KeepTogether([
            _day_header(label, time_note, header_color, styles),
            _spacer(0.15),
        ])
    ]
    paras = [_render_item(it, styles) for it in day_data.get("items", [])]
    phrase = day_data.get("self_test_phrase", "")
    if phrase:
        paras.append(Paragraph("", styles['body']))
        paras.append(Paragraph(_normalize_blanks(phrase), styles['self_test']))
    elements.append(_box(paras, bg, border))
    elements.append(_spacer(0.3))
    return elements


# ─── 月度 Day1/Day2 渲染（两天总复盘）──────────────────────────────────────
def _render_month_day1(day_data: dict, styles: dict) -> list:
    return _render_day1(day_data, styles, C_PURPLE_BG, C_PURPLE_BD)


# ─── 题库渲染 ──────────────────────────────────────────────────────────────────
def _render_quiz_section(questions: list, styles: dict, show_answers=False) -> list:
    if not questions:
        return []
    elements = []
    hdr = Paragraph("📚  题库（自测用）", ParagraphStyle(
        'qhdr', fontName=FONT_MAIN, fontSize=12.5, leading=22, textColor=colors.white))
    hdr_tbl = Table([[hdr]], colWidths=[CONTENT_W])
    hdr_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_HEADER),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
    ]))
    elements.append(hdr_tbl)
    elements.append(_spacer(0.15))

    # 按 category 分组
    cats: dict[str, list] = {}
    for q in questions:
        c = q.get("category", "综合")
        cats.setdefault(c, []).append(q)

    for cat, qs in cats.items():
        elements.append(Paragraph(f"▶ {cat}", ParagraphStyle(
            'cat', fontName=FONT_MAIN, fontSize=10, leading=18,
            textColor=C_HEADER, spaceBefore=4, spaceAfter=2)))
        paras = []
        for i, q in enumerate(qs, 1):
            q_text = f"{i}. {q.get('question', '')}"
            paras.append(Paragraph(q_text, styles['q_q']))
            if show_answers:
                paras.append(Paragraph(f"答：{q.get('answer','')}", styles['q_a']))
            else:
                paras.append(Paragraph(f"答：{BLANK * 2}", styles['q_a']))
        elements.append(_box(paras, C_LIGHT_BG, C_BORDER))
        elements.append(_spacer(0.15))
    return elements


# ─── 周复盘渲染 ────────────────────────────────────────────────────────────────
def _render_weekly_review(prompts: list, styles: dict) -> list:
    if not prompts:
        prompts = [
            "这周哪个知识点最容易忘？",
            "哪天的复习最有效？原因是",
            "下周做题前要额外注意：",
            "我需要老师再讲一遍的是：",
        ]
    elements = [
        HRFlowable(width=CONTENT_W, thickness=1, color=C_GREY, spaceAfter=8),
    ]
    hdr = Paragraph("🗓  周复盘（每周结束后填写）", ParagraphStyle(
        'whdr', fontName=FONT_MAIN, fontSize=11.5, leading=20, textColor=colors.white))
    hdr_tbl = Table([[hdr]], colWidths=[CONTENT_W])
    hdr_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_HEADER),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
    ]))
    elements.append(hdr_tbl)
    elements.append(_spacer(0.15))
    paras = [Paragraph(f"{i+1}. {p}　{BLANK * 2}", styles['fill'])
             for i, p in enumerate(prompts)]
    elements.append(_box(paras, C_LIGHT_BG, C_BORDER))
    elements.append(_spacer(0.25))
    elements.append(Paragraph(
        "★ 执行方法：每天练前 闭眼30秒回忆主题 → 翻笔记1分钟 → 说出1条提醒 → 口头自测1–2分钟",
        styles['tip']))
    elements.append(Paragraph(
        "★ 本讲义由系统课后自动生成，每节新课后更新。填完请保存，期末可一起回顾。",
        styles['tip']))
    return elements


# ─── 主入口：生成单节课 PDF ────────────────────────────────────────────────────
def generate_lesson_pdf(plan_data: dict, output_path: str,
                        show_quiz_answers: bool = False) -> str:
    """
    根据 plan_data（AI 生成的结构化计划）生成单节课复习 PDF。
    返回生成的 PDF 绝对路径。
    """
    _ensure_fonts()
    styles = _make_styles()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title="复习计划讲义（学生填写版）",
    )

    info = plan_data.get("lesson_info", {})
    subject = info.get("subject", "")
    grade   = info.get("grade", "")
    topic   = info.get("topic", "")
    date_   = info.get("date", "")
    cats    = info.get("key_categories", [])
    weak    = plan_data.get("weak_points_summary", "")

    # 标题
    story = [
        _spacer(0.4),
        Paragraph(f"{subject}　复习计划讲义", styles['title']),
        Paragraph("学生填写版　·　每天5分钟以内　·　课后8天跟踪复习", styles['subtitle']),
    ]
    meta_parts = [p for p in [date_, grade, topic] if p]
    if meta_parts:
        story.append(Paragraph("　·　".join(meta_parts), styles['meta']))
    if cats:
        story.append(Paragraph(f"本课知识板块：{'　▪　'.join(cats)}", styles['meta']))
    if weak:
        story.append(Paragraph(f"薄弱点提示：{weak}", styles['meta']))
    story.append(HRFlowable(width=CONTENT_W, thickness=1.5, color=C_HEADER, spaceAfter=10))

    # 天数
    days = plan_data.get("days", [])
    for day_data in days:
        day_type = day_data.get("type", "daily")
        if day_type == "day1":
            story.extend(_render_day1(day_data, styles, C_LIGHT_BG, C_BORDER))
        elif day_type == "month_day1":
            story.extend(_render_month_day1(day_data, styles))
        else:
            story.extend(_render_daily(day_data, styles, C_GREEN_BG, C_GREEN_BD, C_DAILY))

    # 题库
    questions = plan_data.get("questions", [])
    story.extend(_render_quiz_section(questions, styles, show_answers=show_quiz_answers))

    # 周复盘
    story.extend(_render_weekly_review(
        plan_data.get("weekly_review_prompts", []), styles))

    doc.build(story)
    return str(Path(output_path).resolve())


# ─── 主入口：生成月度 PDF ──────────────────────────────────────────────────────
def generate_monthly_pdf(plan_data: dict, output_path: str,
                         show_quiz_answers: bool = False) -> str:
    """
    生成月度综合复习 PDF（多节课聚合）。
    plan_data 结构与单节课相同，但 days 通常有 14 天。
    返回生成的 PDF 绝对路径。
    """
    _ensure_fonts()
    styles = _make_styles()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title="月度综合复习讲义（学生填写版）",
    )

    info    = plan_data.get("lesson_info", {})
    subject = info.get("subject", "")
    month   = info.get("month", info.get("date", ""))
    topic   = info.get("topic", f"{month} 综合复习")
    cats    = info.get("key_categories", [])
    weak    = plan_data.get("weak_points_summary", "")

    story = [
        _spacer(0.4),
        Paragraph(f"{subject}　月度综合复习讲义", styles['title']),
        Paragraph("学生填写版　·　每天5分钟以内　·　14天全月追踪复习", styles['subtitle']),
    ]
    if month:
        story.append(Paragraph(f"复习月份：{month}", styles['meta']))
    if cats:
        story.append(Paragraph(f"本月知识板块（合并）：{'　▪　'.join(cats)}", styles['meta']))
    if weak:
        story.append(Paragraph(f"本月薄弱点：{weak}", styles['meta']))
    story.append(HRFlowable(width=CONTENT_W, thickness=1.5, color=C_MONTH, spaceAfter=10))

    days = plan_data.get("days", [])
    for day_data in days:
        day_type = day_data.get("type", "daily")
        if day_type in ("day1", "month_day1"):
            story.extend(_render_month_day1(day_data, styles))
        else:
            story.extend(_render_daily(day_data, styles, C_PURPLE_BG, C_PURPLE_BD, C_MONTH))

    questions = plan_data.get("questions", [])
    story.extend(_render_quiz_section(questions, styles, show_answers=show_quiz_answers))
    story.extend(_render_weekly_review(
        plan_data.get("weekly_review_prompts", []), styles))

    doc.build(story)
    return str(Path(output_path).resolve())


# ─── 周报 PDF（班级专用，发给老师）────────────────────────────────────────────────
def generate_weekly_pdf(lessons: list, class_info: dict,
                        week_str: str, output_path: str) -> str:
    """
    生成班级周报 PDF，供老师查阅。
    lessons: lesson dict 列表，每个包含 plan 字段（已解析的 JSON dict）。
    class_info: classes 表中的班级记录 dict。
    week_str: 'YYYY-WXX' 格式。
    """
    from datetime import datetime, timedelta
    _ensure_fonts()
    styles = _make_styles()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 计算周日期范围
    year, wk = int(week_str.split("-W")[0]), int(week_str.split("-W")[1])
    monday = datetime.fromisocalendar(year, wk, 1)
    sunday = monday + timedelta(days=6)
    week_range = f"{monday.strftime('%Y年%m月%d日')}—{sunday.strftime('%m月%d日')}"

    class_name    = class_info.get("name", "")
    teacher_name  = class_info.get("teacher_name", "")
    subject       = class_info.get("subject", "")
    grade         = class_info.get("grade", "")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"{class_name} 第{wk}周复习方案",
    )

    # ── 封面区域 ──────────────────────────────────────────────────────────────
    story = [
        _spacer(0.4),
        Paragraph("班级周复习方案　·　老师收阅版", styles['subtitle']),
        Paragraph(f"{class_name}　{grade}{subject}", styles['title']),
        Paragraph(f"第 {wk} 周　{week_range}", styles['meta']),
    ]
    if teacher_name:
        story.append(Paragraph(f"老师：{teacher_name}", styles['meta']))
    story.append(Paragraph(f"本周共 {len(lessons)} 节课", styles['meta']))
    story.append(HRFlowable(width=CONTENT_W, thickness=2, color=C_DAY1, spaceAfter=14))

    # ── 本周课程一览表 ────────────────────────────────────────────────────────
    table_data = [["日期", "本节主题", "核心知识板块", "本节薄弱点"]]
    for les in lessons:
        plan = les.get("plan") or {}
        info = plan.get("lesson_info", {})
        cats = "　".join(info.get("key_categories", [])[:3])
        table_data.append([
            les.get("date", ""),
            les.get("topic", ""),
            cats,
            (les.get("weak_points", "") or "")[:30],
        ])

    col_w = [2.2 * cm, 4.5 * cm, 6.5 * cm, 4.0 * cm]
    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), C_DAY1),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
        ('FONTNAME',     (0, 0), (-1, -1), FONT_MAIN),
        ('FONTSIZE',     (0, 0), (-1, 0), 9),
        ('FONTSIZE',     (0, 1), (-1, -1), 8.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f8ff')]),
        ('GRID',         (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(_spacer(0.5))

    # ── 逐节课复习内容详情 ────────────────────────────────────────────────────
    for i, les in enumerate(lessons, 1):
        plan = les.get("plan") or {}
        info = plan.get("lesson_info", {})
        topic_str = les.get("topic", "") or info.get("topic", "")
        cats = info.get("key_categories", [])
        weak = plan.get("weak_points_summary", "") or les.get("weak_points", "")
        date_str = les.get("date", "")

        # 课节标题
        story.append(KeepTogether([
            Paragraph(
                f"第 {i} 课　{date_str}　　{topic_str}",
                styles['day_title']
            ),
        ]))
        if cats:
            story.append(Paragraph(
                f"知识板块：{'　▪　'.join(cats)}", styles['meta']))
        if weak:
            story.append(Paragraph(f"薄弱点：{weak}", styles['meta']))

        # Day 1 复习内容（第一天总复盘最有参考价值）
        days = plan.get("days", [])
        day1 = next((d for d in days if d.get("type") in ("day1",)), None)
        if day1:
            story.extend(_render_day1(day1, styles, C_LIGHT_BG, C_BORDER))
        else:
            # 没有 day1 就显示所有天
            for day_data in days[:3]:
                story.extend(_render_daily(day_data, styles,
                                           C_LIGHT_BG, C_BORDER, C_DAY1))

        # 本节题库（前 10 题）
        questions = plan.get("questions", [])[:10]
        if questions:
            story.append(Paragraph("本节题库（前10题）", styles['section']))
            for qi, q in enumerate(questions, 1):
                story.append(Paragraph(
                    f"Q{qi}. {q.get('question','')}",
                    styles['body']))
                story.append(Paragraph(
                    f"　　答：{q.get('answer','')}",
                    ParagraphStyle('ans', parent=styles['body'],
                                   textColor=colors.HexColor('#1a6b3c'),
                                   leftIndent=10)))
            story.append(_spacer(0.3))

        story.append(HRFlowable(
            width=CONTENT_W, thickness=0.5,
            color=colors.HexColor('#cccccc'), spaceAfter=10))

    doc.build(story)
    return str(Path(output_path).resolve())

