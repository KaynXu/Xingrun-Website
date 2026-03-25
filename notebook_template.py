#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cornell Notes 风格 PDF 模板生成器
参考设计：Student Notebook（暖米色 + 右侧页码标签 + Cornell 双栏 + 摘要区）
"""

import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ─── 颜色定义 ──────────────────────────────────────────────────────────────────
C_BG          = colors.HexColor('#FAFAF8')   # 页面底色（极浅暖白）
C_TAB         = colors.HexColor('#A8C4D0')   # 右侧标签栏（淡钢蓝）
C_TAB_TEXT    = colors.white
C_HEADER_LINE = colors.HexColor('#CCCCCC')   # 分隔线
C_LABEL       = colors.HexColor('#888888')   # 字段标签（SUBJECT / DATE）
C_TEXT        = colors.HexColor('#1A1A1A')   # 正文颜色
C_LINE        = colors.HexColor('#DDDDDD')   # 横线颜色
C_DIVIDER     = colors.HexColor('#BBBBBB')   # 列分隔线
C_SUMMARY_BG  = colors.HexColor('#F0F0EE')   # 摘要区背景
C_KEYWORD_BG  = colors.HexColor('#F5F5F3')   # 关键词区背景
C_BORDER      = colors.HexColor('#CCCCCC')

# ─── 尺寸定义 ──────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4                  # 595.28 x 841.89 pt

TAB_W         = 0.75 * cm           # 右侧标签栏宽度
TAB_COUNT     = 16                  # 页码标签数量
MARGIN_L      = 1.5 * cm
MARGIN_R      = 1.5 * cm + TAB_W   # 右留出标签区
MARGIN_T      = 1.5 * cm
MARGIN_B      = 1.5 * cm

CONTENT_W     = PAGE_W - MARGIN_L - MARGIN_R
CONTENT_H     = PAGE_H - MARGIN_T - MARGIN_B

HEADER_H      = 1.8 * cm           # 顶部 SUBJECT/DATE 行高
KW_H          = 0.9 * cm           # KEYWORDS 行高
SUMMARY_H     = 3.5 * cm           # 底部 SUMMARY 区高度
NOTES_H       = CONTENT_H - HEADER_H - KW_H - SUMMARY_H  # 笔记区高度

CUE_W         = CONTENT_W * 0.28   # 左侧 CUE 列宽
NOTES_W       = CONTENT_W - CUE_W  # 右侧笔记列宽

LINE_GAP      = 0.72 * cm          # 横线间距
FONT_LABEL    = 7.5                 # 标签字号
FONT_BODY     = 10                  # 正文字号

# ─── 字体注册 ──────────────────────────────────────────────────────────────────
_FONTS_READY = False

def _ensure_fonts():
    global _FONTS_READY
    if _FONTS_READY:
        return
    import platform
    plat = platform.system()
    if plat == 'Darwin':
        pairs = [
            ('/System/Library/Fonts/STHeiti Medium.ttc',
             '/System/Library/Fonts/STHeiti Light.ttc'),
        ]
    elif plat == 'Windows':
        pairs = [('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/msyhl.ttc')]
    else:
        pairs = [('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                  '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc')]

    for main, light in pairs:
        if Path(main).exists():
            try:
                pdfmetrics.registerFont(TTFont('NB_Main',  main,  subfontIndex=0))
                pdfmetrics.registerFont(TTFont('NB_Light', light, subfontIndex=0))
            except Exception:
                pdfmetrics.registerFont(TTFont('NB_Main',  main))
                pdfmetrics.registerFont(TTFont('NB_Light', light))
            _FONTS_READY = True
            return

    # fallback
    pdfmetrics.registerFont(TTFont('NB_Main',  'Helvetica'))
    pdfmetrics.registerFont(TTFont('NB_Light', 'Helvetica'))
    _FONTS_READY = True


# ─── 核心绘制函数 ───────────────────────────────────────────────────────────────

def _draw_background(c: canvas.Canvas):
    """页面底色"""
    c.setFillColor(C_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def _draw_tab_strip(c: canvas.Canvas, current_page: int = 1):
    """右侧蓝色页码标签栏"""
    strip_x = PAGE_W - TAB_W
    strip_h = PAGE_H - MARGIN_T - MARGIN_B
    tab_h   = strip_h / TAB_COUNT
    strip_y_top = PAGE_H - MARGIN_T

    for i in range(TAB_COUNT):
        tab_num = i + 1
        y = strip_y_top - (i + 1) * tab_h
        # 当前页高亮
        if tab_num == current_page:
            c.setFillColor(colors.HexColor('#6B9DAF'))
        else:
            c.setFillColor(C_TAB)
        c.rect(strip_x, y, TAB_W, tab_h, fill=1, stroke=0)
        # 分隔线
        c.setStrokeColor(colors.white)
        c.setLineWidth(0.5)
        c.line(strip_x, y + tab_h, strip_x + TAB_W, y + tab_h)
        # 页码数字
        c.setFillColor(C_TAB_TEXT)
        c.setFont('NB_Main', 7)
        c.drawCentredString(strip_x + TAB_W / 2, y + tab_h / 2 - 3, str(tab_num))

    # 标签栏左侧竖线
    c.setStrokeColor(C_HEADER_LINE)
    c.setLineWidth(0.5)
    c.line(strip_x, MARGIN_B, strip_x, PAGE_H - MARGIN_T)


def _draw_header(c: canvas.Canvas, subject: str = '', date: str = '', keywords: str = ''):
    """顶部 SUBJECT | DATE 行 + KEYWORDS 行"""
    x0 = MARGIN_L
    y_top = PAGE_H - MARGIN_T

    # ── SUBJECT + DATE 行 ──
    row_y = y_top - HEADER_H

    # 背景（白色，让 header 与正文区分）
    c.setFillColor(colors.white)
    c.rect(x0, row_y, CONTENT_W, HEADER_H, fill=1, stroke=0)

    # SUBJECT 标签
    c.setFillColor(C_LABEL)
    c.setFont('NB_Main', FONT_LABEL)
    c.drawString(x0 + 4, row_y + HEADER_H - 14, 'SUBJECT')
    # SUBJECT 值
    c.setFillColor(C_TEXT)
    c.setFont('NB_Main', 11)
    c.drawString(x0 + 4, row_y + 6, subject or '')

    # DATE 标签（右对齐区域）
    date_area_w = 3.5 * cm
    date_x = x0 + CONTENT_W - date_area_w
    c.setFillColor(C_LABEL)
    c.setFont('NB_Main', FONT_LABEL)
    c.drawString(date_x, row_y + HEADER_H - 14, 'DATE')
    # DATE 斜线填写框 "__ / __"
    c.setFillColor(C_TEXT)
    c.setFont('NB_Light', 10)
    c.drawString(date_x, row_y + 6, date or '   /   ')

    # 垂直分隔线（SUBJECT 与 DATE 之间）
    c.setStrokeColor(C_HEADER_LINE)
    c.setLineWidth(0.5)
    c.line(date_x - 6, row_y + 4, date_x - 6, row_y + HEADER_H - 4)

    # header 底部横线
    c.setStrokeColor(C_HEADER_LINE)
    c.setLineWidth(0.8)
    c.line(x0, row_y, x0 + CONTENT_W, row_y)

    # ── KEYWORDS 行 ──
    kw_y = row_y - KW_H
    c.setFillColor(C_KEYWORD_BG)
    c.rect(x0, kw_y, CONTENT_W, KW_H, fill=1, stroke=0)
    c.setFillColor(C_LABEL)
    c.setFont('NB_Main', FONT_LABEL)
    c.drawString(x0 + 4, kw_y + KW_H / 2 + 1, 'KEYWORDS')
    c.setFillColor(C_TEXT)
    c.setFont('NB_Light', 9)
    if keywords:
        c.drawString(x0 + 58, kw_y + KW_H / 2 + 1, keywords)
    # keywords 底部线
    c.setStrokeColor(C_HEADER_LINE)
    c.setLineWidth(0.5)
    c.line(x0, kw_y, x0 + CONTENT_W, kw_y)

    return kw_y  # 返回内容区起始 y


def _draw_notes_area(c: canvas.Canvas, notes_top_y: float):
    """Cornell 双栏笔记区 + 横线"""
    x0 = MARGIN_L
    notes_bottom_y = notes_top_y - NOTES_H

    # 整体外框
    c.setFillColor(colors.white)
    c.rect(x0, notes_bottom_y, CONTENT_W, NOTES_H, fill=1, stroke=0)

    # 左 CUE 列背景（微微更浅）
    c.setFillColor(colors.HexColor('#F7F7F5'))
    c.rect(x0, notes_bottom_y, CUE_W, NOTES_H, fill=1, stroke=0)

    # 列分隔线
    divider_x = x0 + CUE_W
    c.setStrokeColor(C_DIVIDER)
    c.setLineWidth(0.8)
    c.line(divider_x, notes_bottom_y, divider_x, notes_top_y)

    # 列标题
    c.setFillColor(C_LABEL)
    c.setFont('NB_Main', FONT_LABEL)
    c.drawString(x0 + 4, notes_top_y - 12, 'CUES / KEYWORDS')
    c.drawString(divider_x + 6, notes_top_y - 12, 'NOTES')

    # 横线（从 notes_top_y - 20 开始，每隔 LINE_GAP 画一条）
    c.setStrokeColor(C_LINE)
    c.setLineWidth(0.4)
    y = notes_top_y - 20
    while y > notes_bottom_y + 4:
        c.line(x0 + 2, y, x0 + CONTENT_W - 2, y)
        y -= LINE_GAP

    # 外框线
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.6)
    c.rect(x0, notes_bottom_y, CONTENT_W, NOTES_H, fill=0, stroke=1)

    return notes_bottom_y


def _draw_summary(c: canvas.Canvas, summary_top_y: float, summary_text: str = ''):
    """底部 SUMMARY 区"""
    x0 = MARGIN_L
    summary_bottom_y = summary_top_y - SUMMARY_H

    c.setFillColor(C_SUMMARY_BG)
    c.rect(x0, summary_bottom_y, CONTENT_W, SUMMARY_H, fill=1, stroke=0)

    # SUMMARY 标签
    c.setFillColor(C_LABEL)
    c.setFont('NB_Main', FONT_LABEL)
    c.drawString(x0 + 4, summary_top_y - 12, 'SUMMARY')

    # 分隔线
    c.setStrokeColor(C_HEADER_LINE)
    c.setLineWidth(0.5)
    c.line(x0, summary_top_y - 16, x0 + CONTENT_W, summary_top_y - 16)

    # summary 横线
    c.setStrokeColor(C_LINE)
    c.setLineWidth(0.4)
    y = summary_top_y - 28
    while y > summary_bottom_y + 4:
        c.line(x0 + 2, y, x0 + CONTENT_W - 2, y)
        y -= LINE_GAP

    # 外框
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.6)
    c.rect(x0, summary_bottom_y, CONTENT_W, SUMMARY_H, fill=0, stroke=1)

    # 如有预填文字
    if summary_text:
        c.setFillColor(C_TEXT)
        c.setFont('NB_Light', 9)
        c.drawString(x0 + 6, summary_top_y - 30, summary_text)


# ─── 公开 API ───────────────────────────────────────────────────────────────────

def generate_notebook_page(
    output_path: str,
    subject: str = '',
    date:    str = '',
    keywords: str = '',
    summary: str = '',
    current_page: int = 1,
    total_pages: int = 1,
):
    """
    生成单页 Cornell Notes 模板 PDF。

    Args:
        output_path:  输出文件路径（.pdf）
        subject:      科目名称
        date:         日期，如 "2026 / 03 / 25"
        keywords:     关键词
        summary:      摘要预填文字
        current_page: 当前高亮的右侧标签页码
        total_pages:  本 PDF 共几页（循环生成时使用）
    """
    _ensure_fonts()
    c = canvas.Canvas(output_path, pagesize=A4)

    for page_num in range(1, total_pages + 1):
        _draw_background(c)
        _draw_tab_strip(c, current_page=page_num)
        kw_bottom = _draw_header(c, subject=subject, date=date, keywords=keywords)
        notes_bottom = _draw_notes_area(c, notes_top_y=kw_bottom)
        _draw_summary(c, summary_top_y=notes_bottom, summary_text=summary)
        c.showPage()

    c.save()
    print(f"✓ 已生成：{output_path}")


# ─── 直接运行时生成示例 ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    out = Path(__file__).parent / 'data' / 'notebook_template_sample.pdf'
    out.parent.mkdir(exist_ok=True)
    generate_notebook_page(
        output_path=str(out),
        subject='呼吸生理学',
        date='2026 / 03 / 25',
        keywords='通气・换气・呼吸调节',
        summary='',
        current_page=1,
        total_pages=16,
    )
