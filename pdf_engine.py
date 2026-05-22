#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 生成引擎（数据驱动版）
可生成：
  - 单节课 8 天复习讲义（学生填写版）
  - 月度综合复习讲义
"""

from __future__ import annotations

import base64
import html
import io
import json
import mimetypes
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    HRFlowable, KeepTogether, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from review_plan_templates.generate_review_pdfs import normalize_portable_text

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
        # 最后备用：用内置 Helvetica（中文会显示为方块，但不崩溃）
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

# ─── Cornell Notes 模板常量 ────────────────────────────────────────────
NB_TAB_W  = 0.75 * cm
NB_ML     = 1.5  * cm
NB_MR     = 1.5  * cm + NB_TAB_W
NB_MT     = 1.5  * cm
NB_MB     = 1.5  * cm
NB_CW     = PAGE_W - NB_ML - NB_MR
NB_CH     = PAGE_H - NB_MT - NB_MB
NB_HDR_H  = 1.8  * cm
NB_KW_H   = 0.9  * cm
NB_SUM_H  = 3.5  * cm
NB_NOTES_H = NB_CH - NB_HDR_H - NB_KW_H - NB_SUM_H
NB_CUE_W  = NB_CW * 0.28
NB_COL_W  = NB_CW - NB_CUE_W
NB_LINE_H = 1.05 * cm
NB_TAB_N  = 16

NB_BG     = colors.HexColor('#FAFAF8')
NB_TAB    = colors.HexColor('#A8C4D0')
NB_TABHI  = colors.HexColor('#6B9DAF')
NB_HLINE  = colors.HexColor('#CCCCCC')
NB_LBL    = colors.HexColor('#888888')
NB_TXT    = colors.HexColor('#1A1A1A')
NB_RULE   = colors.HexColor('#DDDDDD')
NB_DIV    = colors.HexColor('#BBBBBB')
NB_SUMBG  = colors.HexColor('#F0F0EE')
NB_KWBG   = colors.HexColor('#F5F5F3')
NB_BRD    = colors.HexColor('#CCCCCC')
NB_STEP   = colors.HexColor('#2e6da4')
NB_GRN    = colors.HexColor('#3a7d44')
NB_ANS    = colors.HexColor('#1a6b3c')
NB_PHRASE = colors.HexColor('#c0392b')


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
        'answer': ParagraphStyle('answer', fontName=FONT_MAIN, fontSize=9.5,
                                 leading=17, textColor=colors.HexColor('#1a6b3c'),
                                 leftIndent=24, spaceAfter=3),
    }


# ─── 低级渲染助手 ───────────────────────────────────────────────────────────────
_GREEK = {
    'alpha':'α','beta':'β','gamma':'γ','delta':'δ','epsilon':'ε','zeta':'ζ',
    'eta':'η','theta':'θ','iota':'ι','kappa':'κ','lambda':'λ','mu':'μ',
    'nu':'ν','xi':'ξ','pi':'π','rho':'ρ','sigma':'σ','tau':'τ',
    'upsilon':'υ','phi':'φ','chi':'χ','psi':'ψ','omega':'ω',
    'Alpha':'Α','Beta':'Β','Gamma':'Γ','Delta':'Δ','Theta':'Θ',
    'Lambda':'Λ','Pi':'Π','Sigma':'Σ','Omega':'Ω',
}
_SUP = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶',
        '7':'⁷','8':'⁸','9':'⁹','+':'⁺','-':'⁻','n':'ⁿ',
        'a':'ᵃ','b':'ᵇ','c':'ᶜ','d':'ᵈ','e':'ᵉ','f':'ᶠ',
        'g':'ᵍ','h':'ʰ','i':'ⁱ','j':'ʲ','k':'ᵏ','l':'ˡ',
        'm':'ᵐ','o':'ᵒ','p':'ᵖ','r':'ʳ','s':'ˢ','t':'ᵗ',
        'u':'ᵘ','v':'ᵛ','w':'ʷ','x':'ˣ','y':'ʸ'}
_SUB = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅',
        '6':'₆','7':'₇','8':'₈','9':'₉',
        'a':'ₐ','e':'ₑ','o':'ₒ','x':'ₓ','h':'ₕ',
        'k':'ₖ','l':'ₗ','m':'ₘ','n':'ₙ','p':'ₚ','s':'ₛ','t':'ₜ'}
_MATHBB_SET_MAP = {
    'C': 'ℂ',
    'N': 'ℕ',
    'Q': 'ℚ',
    'R': 'ℝ',
    'Z': 'ℤ',
}
_BARE_LATEX_TEXT_REPLACEMENTS = (
    (r'\infty', '∞'),
    (r'\Rightarrow', '⇒'),
    (r'\Leftarrow', '⇐'),
    (r'\rightarrow', '→'),
    (r'\leftarrow', '←'),
    (r'\subseteq', '⊆'),
    (r'\supseteq', '⊇'),
    (r'\subset', '⊂'),
    (r'\supset', '⊃'),
    (r'\notin', '∉'),
    (r'\approx', '≈'),
    (r'\geq', '≥'),
    (r'\ge', '≥'),
    (r'\leq', '≤'),
    (r'\le', '≤'),
    (r'\neq', '≠'),
    (r'\times', '×'),
    (r'\cdot', '·'),
    (r'\ldots', '...'),
    (r'\cdots', '...'),
    (r'\dots', '...'),
    (r'\div', '÷'),
    (r'\pm', '±'),
    (r'\in', '∈'),
    (r'\to', '→'),
    (r'\left', ''),
    (r'\right', ''),
)
_BROKEN_NEWLINE_LATEX_COMMAND_PATTERN = re.compile(
    r"(?<![。！？.!?：:；;])\n(?=(?:eq\b|otin\b|abla\b|mid\b|parallel\b|subset(?:eq)?\b|supset(?:eq)?\b|rightarrow\b|leftarrow\b|Rightarrow\b|Leftarrow\b|iff\b))"
)
_BROWSER_RENDERER_ENV_KEYS = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "TMPDIR",
    "TEMP",
    "TMP",
    "XDG_RUNTIME_DIR",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "DBUS_SESSION_BUS_ADDRESS",
    "FONTCONFIG_PATH",
    "FONTCONFIG_FILE",
)
_BROWSER_RENDERER_ENV_PREFIXES = (
    "XR_PLAYWRIGHT_",
    "PLAYWRIGHT_",
)


def _render_bare_latex_superscript(content: str) -> str:
    result = []
    for character in content:
        if character in _SUP:
            result.append(_SUP[character])
            continue
        lowered = character.lower()
        if lowered in _SUP:
            result.append(_SUP[lowered])
            continue
        result.append(character)
    return ''.join(result)


def _render_bare_latex_subscript(content: str) -> str:
    result = []
    for character in content:
        if character in _SUB:
            result.append(_SUB[character])
            continue
        lowered = character.lower()
        if lowered in _SUB:
            result.append(_SUB[lowered])
            continue
        return f'_({content})'
    return ''.join(result)


def _normalize_bare_latex_text(text: str) -> str:
    normalized = str(text or "").replace(r'\$', '$')

    for _ in range(5):
        next_value = normalized
        next_value = re.sub(
            r'\\sqrt\[([^\[\]]+)\]\{([^{}]+)\}',
            lambda match: f"{_render_bare_latex_superscript(match.group(1))}√({match.group(2)})",
            next_value,
        )
        next_value = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', next_value)
        next_value = re.sub(r'\\sqrt\{([^{}]+)\}', r'√(\1)', next_value)
        if next_value == normalized:
            break
        normalized = next_value

    normalized = re.sub(r'\\text\{([^{}]+)\}', r'\1', normalized)
    normalized = re.sub(
        r'\\mathbb\s*\{?([A-Za-z])\}?',
        lambda match: _MATHBB_SET_MAP.get(match.group(1), match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r'\^\{([^{}]+)\}',
        lambda match: _render_bare_latex_superscript(match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r'\^([0-9n()+\-=i])',
        lambda match: _render_bare_latex_superscript(match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r'\^([a-zA-Z])',
        lambda match: _render_bare_latex_superscript(match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r'_\{([^{}]+)\}',
        lambda match: _render_bare_latex_subscript(match.group(1)),
        normalized,
    )
    normalized = re.sub(
        r'_([a-zA-Z0-9])',
        lambda match: _render_bare_latex_subscript(match.group(1)),
        normalized,
    )

    for source, target in _BARE_LATEX_TEXT_REPLACEMENTS:
        normalized = normalized.replace(source, target)

    return normalized


def _latex_to_readable(text: str) -> str:
    """将文本中 $...$ 内联 LaTeX 数学公式转为 Unicode 可读字符串。"""
    def _conv(m):
        s = m.group(1)
        # \frac{a}{b} → (a)/(b)，递归处理嵌套
        for _ in range(5):
            s = re.sub(
                r'\\sqrt\[([^\[\]]+)\]\{([^{}]*)\}',
                lambda m: f"{_render_bare_latex_superscript(m.group(1))}√({m.group(2)})",
                s,
            )
            s2 = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', s)
            if s2 == s:
                break
            s = s2
        # \sqrt{x} → √(x)
        s = re.sub(r'\\sqrt\{([^{}]*)\}', r'√(\1)', s)
        # 上标 ^{...} 或 ^x
        s = re.sub(r'\^\{([^{}]*)\}',
                   lambda m: ''.join(_SUP.get(c, _SUP.get(c.lower(), c)) for c in m.group(1)), s)
        s = re.sub(r'\^([0-9a-zA-Z])',
                   lambda m: _SUP.get(m.group(1), m.group(1)), s)
        # 下标 _{...} 或 _x
        def _sub_content(content):
            result = []
            for c in content:
                lc = c.lower()
                if c in _SUB:
                    result.append(_SUB[c])
                elif lc in _SUB:
                    result.append(_SUB[lc])
                else:
                    return f'_({content})'
            return ''.join(result)
        s = re.sub(r'_\{([^{}]*)\}',
                   lambda m: _sub_content(m.group(1)), s)
        s = re.sub(r'_([0-9a-zA-Z])',
                   lambda m: _SUB.get(m.group(1), m.group(1)), s)
        # 希腊字母
        for name, ch in _GREEK.items():
            s = s.replace(f'\\{name}', ch)
        # 常用运算符
        s = (s.replace(r'\times', '×').replace(r'\div', '÷')
              .replace(r'\cdot', '·').replace(r'\geq', '≥')
              .replace(r'\leq', '≤').replace(r'\neq', '≠')
              .replace(r'\approx', '≈').replace(r'\pm', '±')
              .replace(r'\infty', '∞').replace(r'\degree', '°')
              .replace(r'\circ', '°').replace(r'\angle', '∠'))
        # 函数名去反斜杠
        s = re.sub(r'\\(sin|cos|tan|cot|sec|csc|log|lg|ln|lim|max|min)', r'\1', s)
        # 向量箭头
        s = re.sub(r'\\vec\{([^{}]*)\}', r'\1⃗', s)
        # 去掉剩余 \cmd
        s = re.sub(r'\\[a-zA-Z]+', '', s)
        # 去大括号
        s = s.replace('{', '').replace('}', '')
        return s.strip()

    return _normalize_bare_latex_text(
        re.sub(r'\$\$([^$]+)\$\$', _conv,
               re.sub(r'\$([^$]+)\$', _conv, text))
    )


def _normalize_blanks(text: str) -> str:
    """LaTeX→Unicode，____ 替换，XML 特殊字符转义，保证 ReportLab 安全渲染"""
    text = _latex_to_readable(text)
    text = text.replace('____', BLANK)
    return html.escape(text)


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


def _render_item(item: dict, styles: dict, show_answers: bool = False) -> list:
    """Return a list of Paragraphs for this item (may include an answer line)."""
    text = _normalize_blanks(item.get("text", ""))
    t = item.get("type", "body")
    answer = item.get("answer", "")
    result = []
    if t == "fill":
        result.append(Paragraph(text, styles['fill']))
        if show_answers and answer:
            result.append(Paragraph(f"　✔️ 参考答案：{html.escape(answer)}", styles['answer']))
    elif t == "self_test":
        result.append(Paragraph(text, styles['self_test']))
    else:
        result.append(Paragraph(text, styles['body']))
    return result


def _normalize_wrong_question_image_rotation(value: object) -> int:
    try:
        degrees = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return degrees if degrees in {0, 90, 180, 270} else 0


def _rotate_wrong_question_image_bytes(image_bytes: bytes, image_rotation_degrees: object) -> bytes:
    degrees = _normalize_wrong_question_image_rotation(image_rotation_degrees)
    if not degrees:
        return image_bytes
    try:
        with PILImage.open(io.BytesIO(image_bytes)) as source_image:
            rotated_image = source_image.rotate(-degrees, expand=True)
            output = io.BytesIO()
            rotated_image.save(output, format="PNG")
            return output.getvalue()
    except Exception:
        return image_bytes


def _fetch_wrong_question_image_bytes(image_url: str, image_rotation_degrees: object = 0) -> bytes | None:
    normalized_image_url = (image_url or "").strip()
    if not normalized_image_url:
        return None
    try:
        with urllib.request.urlopen(normalized_image_url, timeout=10) as response:
            image_bytes = response.read()
    except (urllib.error.URLError, ValueError, OSError):
        return None
    if not image_bytes:
        return None
    return _rotate_wrong_question_image_bytes(image_bytes, image_rotation_degrees)


def _build_wrong_question_image(image_url: str, image_rotation_degrees: object = 0):
    image_bytes = _fetch_wrong_question_image_bytes(image_url, image_rotation_degrees)
    if not image_bytes:
        return None
    try:
        flowable = Image(io.BytesIO(image_bytes))
    except Exception:
        return None

    max_width = CONTENT_W - 1.2 * cm
    max_height = 11.5 * cm
    draw_width = float(getattr(flowable, "drawWidth", 0) or 0)
    draw_height = float(getattr(flowable, "drawHeight", 0) or 0)
    if draw_width <= 0 or draw_height <= 0:
        return None

    scale = min(max_width / draw_width, max_height / draw_height, 1.0)
    flowable.drawWidth = draw_width * scale
    flowable.drawHeight = draw_height * scale
    flowable.hAlign = 'CENTER'
    return flowable


def _build_wrong_question_geometry_image_card(image_url: str, styles: dict, image_rotation_degrees: object = 0):
    _ensure_fonts()
    title = Paragraph("几何原题图片", styles["section"])
    caption = Paragraph("保留原图入库，便于按图复盘几何关系。", styles["tip"])
    geometry_image = _build_wrong_question_image(image_url, image_rotation_degrees)
    if geometry_image is None:
        image_content = Paragraph("图片暂时无法载入，已保留原图记录。", styles["tip"])
    else:
        image_content = geometry_image

    table = Table(
        [[title], [image_content], [caption]],
        colWidths=[CONTENT_W],
        rowHeights=[None, 12.4 * cm, None],
    )
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fbff')),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#b8cfe6')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 2), (-1, 2), 'LEFT'),
        ('LINEBELOW', (0, 0), (-1, 0), 0.35, colors.HexColor('#d7e5f2')),
        ('LINEABOVE', (0, 2), (-1, 2), 0.35, colors.HexColor('#d7e5f2')),
    ]))
    return table


def _guess_wrong_question_image_mime_type(image_url: str) -> str:
    guessed_type, _ = mimetypes.guess_type(image_url or "")
    if guessed_type and guessed_type.startswith("image/"):
        return guessed_type
    return "image/png"


def _parse_wrong_question_diagram_spec(source: dict) -> tuple[str, dict]:
    diagram_type = str(
        source.get("diagram_type")
        or source.get("diagram_type_snapshot")
        or ""
    ).strip()
    raw_spec = (
        source.get("diagram_spec")
        if source.get("diagram_spec") is not None
        else source.get("diagram_spec_snapshot")
    )
    if raw_spec is None:
        raw_spec = (
            source.get("diagram_spec_json")
            or source.get("diagram_spec_json_snapshot")
            or ""
        )
    if isinstance(raw_spec, str):
        raw_spec = raw_spec.strip()
        if not raw_spec:
            return diagram_type, {}
        try:
            raw_spec = json.loads(raw_spec)
        except json.JSONDecodeError:
            return diagram_type, {}
    if not isinstance(raw_spec, dict):
        return diagram_type, {}
    spec = dict(raw_spec)
    spec_type = str(spec.get("type") or diagram_type or "").strip()
    if spec_type:
        spec["type"] = spec_type
    if not diagram_type:
        diagram_type = spec_type
    return diagram_type, spec


def _diagram_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _diagram_points_by_label(points: list[dict]) -> dict[str, dict]:
    return {
        str(point.get("label") or "").strip(): point
        for point in points
        if isinstance(point, dict) and str(point.get("label") or "").strip()
    }


def _scale_diagram_value(value: float, min_value: float, max_value: float, start: float, end: float) -> float:
    if abs(max_value - min_value) < 1e-9:
        return (start + end) / 2
    return start + (value - min_value) * (end - start) / (max_value - min_value)


def _render_wrong_question_number_line_svg(spec: dict) -> str:
    raw_points = spec.get("points") if isinstance(spec.get("points"), list) else []
    points = [
        {
            "label": str(point.get("label") or "").strip(),
            "value": _diagram_float(point.get("value")),
        }
        for point in raw_points
        if isinstance(point, dict)
    ]
    points = [point for point in points if point["label"]]
    if not points:
        return ""

    values = [point["value"] for point in points]
    min_value = min(values)
    max_value = max(values)
    padding = max(2.0, (max_value - min_value) * 0.18)
    min_value -= padding
    max_value += padding
    width, height = 560, 180
    y = 105
    axis_start, axis_end = 54, width - 54
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{axis_start}" y1="{y}" x2="{axis_end}" y2="{y}" stroke="#111827" stroke-width="3" stroke-linecap="round"/>',
        f'<path d="M {axis_end} {y} l -14 -9 v 18 z" fill="#111827"/>',
    ]
    for point in sorted(points, key=lambda item: item["value"]):
        x = _scale_diagram_value(point["value"], min_value, max_value, axis_start, axis_end - 4)
        label = html.escape(point["label"])
        value_text = html.escape(f"{point['value']:g}")
        elements.extend(
            [
                f'<line x1="{x:.1f}" y1="{y - 11}" x2="{x:.1f}" y2="{y + 11}" stroke="#111827" stroke-width="3"/>',
                f'<text x="{x:.1f}" y="{y - 28}" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-style="italic" font-weight="700" fill="#111827">{label}</text>',
                f'<text x="{x:.1f}" y="{y + 42}" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#6b7280">{value_text}</text>',
            ]
        )
    elements.append("</svg>")
    return "".join(elements)


def _render_wrong_question_geometry_svg(spec: dict) -> str:
    raw_points = spec.get("points") if isinstance(spec.get("points"), list) else []
    points = [
        {
            "label": str(point.get("label") or "").strip(),
            "x": _diagram_float(point.get("x")),
            "y": _diagram_float(point.get("y")),
        }
        for point in raw_points
        if isinstance(point, dict) and str(point.get("label") or "").strip()
    ]
    if not points:
        return ""

    width, height = 560, 340
    margin = 48
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if abs(max_x - min_x) < 1e-9:
        min_x -= 1
        max_x += 1
    if abs(max_y - min_y) < 1e-9:
        min_y -= 1
        max_y += 1

    def project(point: dict) -> tuple[float, float]:
        x = _scale_diagram_value(point["x"], min_x, max_x, margin, width - margin)
        y = _scale_diagram_value(point["y"], min_y, max_y, height - margin, margin)
        return x, y

    point_lookup = _diagram_points_by_label(points)
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    raw_segments = spec.get("segments") if isinstance(spec.get("segments"), list) else []
    for segment in raw_segments:
        if isinstance(segment, dict):
            start_label = str(segment.get("from") or segment.get("start") or "").strip()
            end_label = str(segment.get("to") or segment.get("end") or "").strip()
            dashed = bool(segment.get("dashed") or segment.get("dash"))
        elif isinstance(segment, (list, tuple)) and len(segment) >= 2:
            start_label = str(segment[0] or "").strip()
            end_label = str(segment[1] or "").strip()
            dashed = False
        else:
            continue
        start = point_lookup.get(start_label)
        end = point_lookup.get(end_label)
        if not start or not end:
            continue
        x1, y1 = project(start)
        x2, y2 = project(end)
        dash = ' stroke-dasharray="10 8"' if dashed else ""
        elements.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111827" stroke-width="3" stroke-linecap="round"{dash}/>'
        )
    for point in points:
        x, y = project(point)
        label = html.escape(point["label"])
        elements.extend(
            [
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#111827"/>',
                f'<text x="{x + 9:.1f}" y="{y - 9:.1f}" font-family="Arial, sans-serif" font-size="19" font-style="italic" font-weight="700" fill="#111827">{label}</text>',
            ]
        )
    elements.append("</svg>")
    return "".join(elements)


def _render_wrong_question_function_plot_svg(spec: dict) -> str:
    curves = spec.get("curves") if isinstance(spec.get("curves"), list) else []
    if not curves and isinstance(spec.get("points"), list):
        curves = [{"points": spec.get("points"), "label": spec.get("label") or ""}]

    normalized_curves: list[dict] = []
    all_points: list[tuple[float, float]] = []
    for curve in curves:
        if not isinstance(curve, dict):
            continue
        points = []
        for raw_point in curve.get("points") or []:
            if isinstance(raw_point, dict):
                point = (_diagram_float(raw_point.get("x")), _diagram_float(raw_point.get("y")))
            elif isinstance(raw_point, (list, tuple)) and len(raw_point) >= 2:
                point = (_diagram_float(raw_point[0]), _diagram_float(raw_point[1]))
            else:
                continue
            points.append(point)
            all_points.append(point)
        if points:
            normalized_curves.append({"points": points, "label": str(curve.get("label") or "").strip()})
    if not normalized_curves:
        return ""

    x_min = _diagram_float(spec.get("x_min"), min(point[0] for point in all_points))
    x_max = _diagram_float(spec.get("x_max"), max(point[0] for point in all_points))
    y_min = _diagram_float(spec.get("y_min"), min(point[1] for point in all_points))
    y_max = _diagram_float(spec.get("y_max"), max(point[1] for point in all_points))
    if abs(x_max - x_min) < 1e-9:
        x_min -= 1
        x_max += 1
    if abs(y_max - y_min) < 1e-9:
        y_min -= 1
        y_max += 1

    width, height = 560, 360
    margin = 46

    def project(point: tuple[float, float]) -> tuple[float, float]:
        x = _scale_diagram_value(point[0], x_min, x_max, margin, width - margin)
        y = _scale_diagram_value(point[1], y_min, y_max, height - margin, margin)
        return x, y

    x_axis_y = project((0, 0))[1] if y_min <= 0 <= y_max else height - margin
    y_axis_x = project((0, 0))[0] if x_min <= 0 <= x_max else margin
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{margin}" y1="{x_axis_y:.1f}" x2="{width - margin}" y2="{x_axis_y:.1f}" stroke="#374151" stroke-width="2"/>',
        f'<line x1="{y_axis_x:.1f}" y1="{margin}" x2="{y_axis_x:.1f}" y2="{height - margin}" stroke="#374151" stroke-width="2"/>',
        f'<text x="{width - margin + 10}" y="{x_axis_y + 5:.1f}" font-family="Arial, sans-serif" font-size="16" fill="#374151">x</text>',
        f'<text x="{y_axis_x - 5:.1f}" y="{margin - 14}" font-family="Arial, sans-serif" font-size="16" fill="#374151">y</text>',
    ]
    palette = ["#2563eb", "#dc2626", "#059669"]
    for index, curve in enumerate(normalized_curves):
        projected = [project(point) for point in curve["points"]]
        path_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in projected)
        color = palette[index % len(palette)]
        elements.append(
            f'<polyline points="{path_points}" fill="none" stroke="{color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        label = html.escape(curve["label"])
        if label:
            label_x, label_y = projected[-1]
            elements.append(
                f'<text x="{label_x + 8:.1f}" y="{label_y - 8:.1f}" font-family="Arial, sans-serif" font-size="16" fill="{color}">{label}</text>'
            )
    elements.append("</svg>")
    return "".join(elements)


def _render_wrong_question_diagram_data_url(source: dict) -> tuple[str, str]:
    diagram_type, spec = _parse_wrong_question_diagram_spec(source)
    if not spec:
        return "", diagram_type
    spec_type = str(spec.get("type") or diagram_type or "").strip().lower()
    if spec_type == "number_line":
        svg = _render_wrong_question_number_line_svg(spec)
    elif spec_type in {"geometry", "coordinate_geometry", "geometric"}:
        svg = _render_wrong_question_geometry_svg(spec)
    elif spec_type in {"function_plot", "function", "graph"}:
        svg = _render_wrong_question_function_plot_svg(spec)
    else:
        svg = ""
    if not svg:
        return "", diagram_type
    encoded_svg = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded_svg}", diagram_type or spec_type


def _repair_wrong_question_latex_transport(text: str) -> str:
    if not isinstance(text, str) or not text:
        return str(text or "")

    repaired = text.replace("\r\n", "\n")
    repaired = repaired.replace("\t", "\\t")
    repaired = repaired.replace("\f", "\\f")
    repaired = repaired.replace("\b", "\\b")
    repaired = repaired.replace("\r", "\\r")
    repaired = _BROKEN_NEWLINE_LATEX_COMMAND_PATTERN.sub(r"\\n", repaired)
    return repaired


def _build_portable_wrong_question_text(value: str) -> str:
    repaired = _repair_wrong_question_latex_transport(str(value or ""))
    repaired = re.sub(r"\\text\{([^{}]+)\}", r"\1", repaired)
    repaired = repaired.replace(r"\rightarrow", "XRRIGHTARROWTOKEN")
    repaired = repaired.replace(r"\leftarrow", "XRLEFTARROWTOKEN")
    repaired = repaired.replace(r"\to", "XRARROWTOKEN")
    portable = normalize_portable_text(_normalize_bare_latex_text(repaired))
    portable = portable.replace("XRRIGHTARROWTOKEN", "→")
    portable = portable.replace("XRLEFTARROWTOKEN", "←")
    portable = portable.replace("XRARROWTOKEN", "→")
    portable = portable.replace("lim_(", "lim(")
    return portable


def _build_browser_wrong_question_library_records(records: list[dict]) -> list[dict]:
    browser_records: list[dict] = []

    for record in records:
        normalized_record = {
            "created_at": str(record.get("created_at") or ""),
            "is_geometry": bool(record.get("is_geometry")),
            "question_text": _repair_wrong_question_latex_transport(str(record.get("question_text") or "")),
            "diagram_type": str(record.get("diagram_type") or "").strip(),
            "child_reason_text": str(
                record.get("child_raw_reason_text")
                or record.get("child_reason_text")
                or ""
            ),
            "cause_note": str(
                record.get("secondary_error_summary")
                or record.get("cause_note")
                or ""
            ),
            "core_issue": str(record.get("child_reason_core_issue") or record.get("core_issue") or ""),
            "key_omission": str(record.get("child_reason_key_omission") or record.get("key_omission") or ""),
            "next_step": str(record.get("child_reason_next_step") or record.get("next_step") or ""),
            "image_data_url": "",
        }

        diagram_data_url, diagram_type = _render_wrong_question_diagram_data_url(record)
        if diagram_data_url:
            normalized_record["image_data_url"] = diagram_data_url
            normalized_record["diagram_type"] = diagram_type
        elif normalized_record["is_geometry"]:
            image_url = str(record.get("image_url") or "")
            image_bytes = _fetch_wrong_question_image_bytes(image_url, record.get("image_rotation_degrees"))
            if image_bytes:
                encoded_bytes = base64.b64encode(image_bytes).decode("ascii")
                normalized_record["image_data_url"] = (
                    f"data:{_guess_wrong_question_image_mime_type(image_url)};base64,{encoded_bytes}"
                )

        browser_records.append(normalized_record)

    return browser_records


def _build_browser_wrong_question_practice_items(items: list[dict]) -> list[dict]:
    browser_items: list[dict] = []

    for item in items:
        practice_item_id = str(
            item.get("practice_item_id") or item.get("wrong_question_record_id") or ""
        ).strip()
        key_steps = []
        if isinstance(item.get("key_steps"), list):
            key_steps = [
                str(step).strip()
                for step in item.get("key_steps", [])
                if str(step).strip()
            ]
        normalized_item = {
            "question_order": int(item.get("question_order") or 0),
            "wrong_question_record_id": str(item.get("wrong_question_record_id") or ""),
            "is_geometry": bool(item.get("is_geometry")),
            "question_text_snapshot": _repair_wrong_question_latex_transport(str(item.get("question_text_snapshot") or "")),
            "diagram_type": str(item.get("diagram_type") or item.get("diagram_type_snapshot") or "").strip(),
            "ai_hint": str(item.get("ai_hint") or ""),
            "reason_blank_prompt": str(item.get("reason_blank_prompt") or ""),
            "improvement_summary_prompt": str(item.get("improvement_summary_prompt") or ""),
            "image_data_url": "",
            "practiceItemId": practice_item_id,
            "itemType": str(item.get("item_type") or "real").strip() or "real",
            "trainingGoal": str(item.get("training_goal") or "").strip(),
            "answer": str(item.get("answer") or "").strip(),
            "keySteps": key_steps,
            "pitfallReminder": str(item.get("pitfall_reminder") or "").strip(),
            "scheduledDate": str(item.get("scheduled_date") or "").strip(),
        }

        diagram_data_url, diagram_type = _render_wrong_question_diagram_data_url(item)
        if diagram_data_url:
            normalized_item["image_data_url"] = diagram_data_url
            normalized_item["diagram_type"] = diagram_type
        elif normalized_item["is_geometry"]:
            image_url = str(item.get("image_url_snapshot") or "")
            image_bytes = _fetch_wrong_question_image_bytes(image_url)
            if image_bytes:
                encoded_bytes = base64.b64encode(image_bytes).decode("ascii")
                normalized_item["image_data_url"] = (
                    f"data:{_guess_wrong_question_image_mime_type(image_url)};base64,{encoded_bytes}"
                )

        browser_items.append(normalized_item)

    return browser_items


def _build_browser_wrong_question_practice_schedule(schedule: list[dict]) -> list[dict]:
    browser_schedule: list[dict] = []

    for day in schedule:
        if not isinstance(day, dict):
            continue
        browser_schedule.append(
            {
                "dayIndex": int(day.get("day_index") or 0),
                "date": str(day.get("date") or "").strip(),
                "items": _build_browser_wrong_question_practice_items(day.get("items") or []),
            }
        )

    return browser_schedule


def _build_browser_renderer_failure_message(*, default_message: str, result: subprocess.CompletedProcess) -> str:
    stderr = str(result.stderr or "").strip()
    if stderr:
        return stderr
    stdout = str(result.stdout or "").strip()
    if stdout:
        return stdout
    if int(result.returncode or 0) < 0:
        return f"{default_message}（signal {-int(result.returncode)}）"
    return f"{default_message}（exit code {int(result.returncode or 0)}）"


def _build_browser_renderer_env(source_env: dict[str, str] | None = None) -> dict[str, str]:
    raw_env = os.environ if source_env is None else source_env
    renderer_env = {}

    for key in _BROWSER_RENDERER_ENV_KEYS:
        value = str(raw_env.get(key) or "").strip()
        if value:
            renderer_env[key] = value

    for key, value in raw_env.items():
        if not value:
            continue
        if any(key.startswith(prefix) for prefix in _BROWSER_RENDERER_ENV_PREFIXES):
            renderer_env[key] = str(value)

    if "PATH" not in renderer_env:
        renderer_env["PATH"] = os.defpath

    return renderer_env


def _render_student_wrong_question_library_pdf_via_browser(
    *,
    student_name: str,
    class_name: str,
    teacher_title: str,
    records: list[dict],
    output_path: str,
) -> str:
    project_root = Path(__file__).resolve().parent
    renderer_script = project_root / "frontend" / "scripts" / "renderWrongQuestionLibraryPdf.mjs"

    payload = {
        "studentName": student_name,
        "className": class_name,
        "teacherTitle": teacher_title,
        "records": _build_browser_wrong_question_library_records(records),
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
        json.dump(payload, temp_file, ensure_ascii=False)
        temp_file_path = temp_file.name

    try:
        result = subprocess.run(
            ["node", str(renderer_script), temp_file_path, output_path],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
            env=_build_browser_renderer_env(),
        )
    finally:
        try:
            os.unlink(temp_file_path)
        except FileNotFoundError:
            pass

    if result.returncode != 0:
        error_message = _build_browser_renderer_failure_message(
            default_message="学生错题库 PDF 浏览器渲染失败",
            result=result,
        )
        raise RuntimeError(error_message)

    destination = Path(output_path).resolve()
    if not destination.exists() or destination.stat().st_size <= 0:
        raise RuntimeError("学生错题库 PDF 浏览器渲染失败：输出文件为空")

    return str(destination)


def _render_wrong_question_practice_sheet_pdf_via_browser(
    *,
    student_name: str,
    class_name: str,
    teacher_name: str,
    title: str,
    items: list[dict],
    output_path: str,
    schedule: list[dict] | None = None,
    answer_items: list[dict] | None = None,
    pack_meta: dict | None = None,
) -> str:
    project_root = Path(__file__).resolve().parent
    renderer_script = project_root / "frontend" / "scripts" / "renderWrongQuestionPracticeSheetPdf.mjs"

    payload = {
        "studentName": student_name,
        "className": class_name,
        "teacherName": teacher_name,
        "title": title,
        "items": _build_browser_wrong_question_practice_items(items),
        "schedule": _build_browser_wrong_question_practice_schedule(schedule or []),
        "answerItems": _build_browser_wrong_question_practice_items(answer_items or items),
        "packMeta": {
            "mode": str((pack_meta or {}).get("mode") or "").strip(),
            "target": str((pack_meta or {}).get("target") or "").strip(),
            "volume": str((pack_meta or {}).get("volume") or "").strip(),
            "generatedDate": str((pack_meta or {}).get("generated_date") or "").strip(),
        },
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
        json.dump(payload, temp_file, ensure_ascii=False)
        temp_file_path = temp_file.name

    try:
        result = subprocess.run(
            ["node", str(renderer_script), temp_file_path, output_path],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
            env=_build_browser_renderer_env(),
        )
    finally:
        try:
            os.unlink(temp_file_path)
        except FileNotFoundError:
            pass

    if result.returncode != 0:
        error_message = _build_browser_renderer_failure_message(
            default_message="错题练习 PDF 浏览器渲染失败",
            result=result,
        )
        raise RuntimeError(error_message)

    destination = Path(output_path).resolve()
    if not destination.exists() or destination.stat().st_size <= 0:
        raise RuntimeError("错题练习 PDF 浏览器渲染失败：输出文件为空")

    return str(destination)


def _generate_student_wrong_question_library_pdf_via_reportlab(
    *,
    student_name: str,
    class_name: str,
    records: list[dict],
    output_path: str,
) -> str:
    _ensure_fonts()
    styles = _make_styles()
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=LM,
        rightMargin=RM,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"{student_name} 错题库",
    )

    teacher_names = [
        str(record.get("teacher_display_name") or "").strip()
        for record in records
        if str(record.get("teacher_display_name") or "").strip()
    ]
    teacher_title = "、".join(dict.fromkeys(teacher_names)) or "未分配老师"

    story = [
        _spacer(0.4),
        Paragraph(f"{html.escape(student_name)} 错题库｜任课老师：{html.escape(teacher_title)}", styles["title"]),
        Paragraph(f"班级：{html.escape(class_name)}", styles["meta"]),
        Paragraph(f"错题总数：{len(records)}", styles["meta"]),
        HRFlowable(width=CONTENT_W, thickness=1.2, color=C_DAY1, spaceAfter=10),
    ]

    for index, record in enumerate(records, start=1):
        if index > 1:
            story.append(PageBreak())
        story.append(Paragraph(f"第 {index} 题", styles["section"]))
        story.append(Paragraph(f"上传时间：{html.escape(str(record.get('created_at') or ''))}", styles["body"]))
        if record.get("is_geometry"):
            story.append(Paragraph("题目内容：几何题按图片入库", styles["body"]))
            story.append(_spacer(0.15))
            story.append(_build_wrong_question_geometry_image_card(
                str(record.get("image_url") or ""),
                styles,
                record.get("image_rotation_degrees"),
            ))
            story.append(_spacer(0.1))
        else:
            story.append(
                Paragraph(
                    f"题目内容：{html.escape(_build_portable_wrong_question_text(str(record.get('question_text') or '')))}",
                    styles["body"],
                )
            )
        child_reason_text = str(record.get("child_raw_reason_text") or "").strip()
        cause_note = str(record.get("secondary_error_summary") or "").strip()
        if child_reason_text:
            story.append(
                Paragraph(
                    f"孩子自述错因：{html.escape(child_reason_text)}",
                    styles["body"],
                )
            )
        if cause_note:
            story.append(
                Paragraph(
                    f"补充备注：{html.escape(cause_note)}",
                    styles["body"],
                )
            )

    doc.build(story)
    return str(destination)


def generate_student_wrong_question_library_pdf(
    *,
    student_name: str,
    class_name: str,
    records: list[dict],
    output_path: str,
) -> str:
    teacher_names = [
        str(record.get("teacher_display_name") or "").strip()
        for record in records
        if str(record.get("teacher_display_name") or "").strip()
    ]
    teacher_title = "、".join(dict.fromkeys(teacher_names)) or "未分配老师"

    try:
        return _render_student_wrong_question_library_pdf_via_browser(
            student_name=student_name,
            class_name=class_name,
            teacher_title=teacher_title,
            records=records,
            output_path=output_path,
        )
    except Exception as browser_error:
        try:
            return _generate_student_wrong_question_library_pdf_via_reportlab(
                student_name=student_name,
                class_name=class_name,
                records=records,
                output_path=output_path,
            )
        except Exception as reportlab_error:
            raise RuntimeError(
                "学生错题库 PDF 生成失败：浏览器渲染与 ReportLab 回退都未成功"
            ) from reportlab_error


def generate_wrong_question_practice_sheet_pdf(
    *,
    student_name: str,
    class_name: str,
    teacher_name: str,
    title: str,
    items: list[dict],
    output_path: str,
    schedule: list[dict] | None = None,
    answer_items: list[dict] | None = None,
    pack_meta: dict | None = None,
) -> str:
    return _render_wrong_question_practice_sheet_pdf_via_browser(
        student_name=student_name,
        class_name=class_name,
        teacher_name=teacher_name,
        title=title,
        items=items,
        output_path=output_path,
        schedule=schedule,
        answer_items=answer_items,
        pack_meta=pack_meta,
    )


# ─── Day 1 渲染（step 结构）──────────────────────────────────────────────────
def _render_day1(day_data: dict, styles: dict, bg: colors.Color,
                 border: colors.Color, show_answers: bool = False) -> list:
    elements = [
        KeepTogether([
            _day_header(day_data["label"], day_data.get("time", ""), C_DAY1, styles),
            _spacer(0.15),
        ])
    ]
    steps = day_data.get("steps", [])
    for step in steps:
        elements.append(Paragraph(
            f"{html.escape(step.get('step_label',''))}：<b>{html.escape(step.get('title',''))}</b>",
            styles['section']
        ))
        paras = []
        for it in step.get("items", []):
            paras.extend(_render_item(it, styles, show_answers))
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
                  border: colors.Color, header_color: colors.Color,
                  show_answers: bool = False) -> list:
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
    paras = []
    for it in day_data.get("items", []):
        paras.extend(_render_item(it, styles, show_answers))
    phrase = day_data.get("self_test_phrase", "")
    if phrase:
        paras.append(Paragraph("", styles['body']))
        paras.append(Paragraph(_normalize_blanks(phrase), styles['self_test']))
    elements.append(_box(paras, bg, border))
    elements.append(_spacer(0.3))
    return elements


# ─── 月度 Day1/Day2 渲染（两天总复盘）──────────────────────────────────────
def _render_month_day1(day_data: dict, styles: dict, show_answers: bool = False) -> list:
    return _render_day1(day_data, styles, C_PURPLE_BG, C_PURPLE_BD, show_answers)


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
            q_text = f"{i}. {html.escape(q.get('question', ''))}"
            paras.append(Paragraph(q_text, styles['q_q']))
            if show_answers:
                paras.append(Paragraph(f"答：{html.escape(q.get('answer',''))}", styles['q_a']))
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
    paras = [Paragraph(f"{i+1}. {html.escape(p)}　{BLANK * 2}", styles['fill'])
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


# ─── Cornell Notes 底层绘制工具 ────────────────────────────────────────────────
def _nb_split(text: str, font: str, size: float, max_w: float) -> list:
    """CJK-aware character-level line splitter."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if not text:
        return ['']
    lines, cur = [], ''
    for ch in text:
        test = cur + ch
        try:
            w = stringWidth(test, font, size)
        except Exception:
            w = len(test) * size * 0.65
        if w > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines or ['']


def _nb_draw_page(c, page_num: int, subject: str, date_str: str, keywords: str):
    """Draw a full Cornell Notes page background. Returns (kw_bot, nb_bot)."""
    x0 = NB_ML
    # Background
    c.setFillColor(NB_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Tab strip (right edge)
    sx = PAGE_W - NB_TAB_W
    sh = PAGE_H - NB_MT - NB_MB
    th = sh / NB_TAB_N
    ty = PAGE_H - NB_MT
    hi = ((page_num - 1) % NB_TAB_N) + 1
    for i in range(NB_TAB_N):
        n = i + 1
        y = ty - (i + 1) * th
        c.setFillColor(NB_TABHI if n == hi else NB_TAB)
        c.rect(sx, y, NB_TAB_W, th, fill=1, stroke=0)
        c.setStrokeColor(colors.white)
        c.setLineWidth(0.5)
        c.line(sx, y + th, sx + NB_TAB_W, y + th)
        c.setFillColor(colors.white)
        c.setFont(FONT_MAIN, 7)
        c.drawCentredString(sx + NB_TAB_W / 2, y + th / 2 - 3, str(n))
    c.setStrokeColor(NB_HLINE)
    c.setLineWidth(0.5)
    c.line(sx, NB_MB, sx, PAGE_H - NB_MT)
    # Header: SUBJECT | DATE
    row_y = PAGE_H - NB_MT - NB_HDR_H
    c.setFillColor(colors.white)
    c.rect(x0, row_y, NB_CW, NB_HDR_H, fill=1, stroke=0)
    c.setFillColor(NB_LBL)
    c.setFont(FONT_MAIN, 7.5)
    c.drawString(x0 + 4, row_y + NB_HDR_H - 14, 'SUBJECT')
    c.setFillColor(NB_TXT)
    c.setFont(FONT_MAIN, 10)
    c.drawString(x0 + 4, row_y + 7, subject)
    dw = 3.5 * cm
    dx = x0 + NB_CW - dw
    c.setFillColor(NB_LBL)
    c.setFont(FONT_MAIN, 7.5)
    c.drawString(dx, row_y + NB_HDR_H - 14, 'DATE')
    c.setFillColor(NB_TXT)
    c.setFont(FONT_LIGHT, 9)
    c.drawString(dx, row_y + 7, date_str or '   /   ')
    c.setStrokeColor(NB_HLINE)
    c.setLineWidth(0.5)
    c.line(dx - 6, row_y + 4, dx - 6, row_y + NB_HDR_H - 4)
    c.setLineWidth(0.8)
    c.line(x0, row_y, x0 + NB_CW, row_y)
    # Keywords row
    kw_y = row_y - NB_KW_H
    c.setFillColor(NB_KWBG)
    c.rect(x0, kw_y, NB_CW, NB_KW_H, fill=1, stroke=0)
    c.setFillColor(NB_LBL)
    c.setFont(FONT_MAIN, 7.5)
    c.drawString(x0 + 4, kw_y + NB_KW_H / 2 + 1, 'KEYWORDS')
    c.setFillColor(NB_TXT)
    c.setFont(FONT_LIGHT, 9)
    if keywords:
        c.drawString(x0 + 58, kw_y + NB_KW_H / 2 + 1, keywords[:88])
    c.setStrokeColor(NB_HLINE)
    c.setLineWidth(0.5)
    c.line(x0, kw_y, x0 + NB_CW, kw_y)
    kw_bot = kw_y
    # Notes two-column area
    nb_bot = kw_bot - NB_NOTES_H
    c.setFillColor(colors.white)
    c.rect(x0, nb_bot, NB_CW, NB_NOTES_H, fill=1, stroke=0)
    c.setFillColor(colors.HexColor('#F7F7F5'))
    c.rect(x0, nb_bot, NB_CUE_W, NB_NOTES_H, fill=1, stroke=0)
    dvx = x0 + NB_CUE_W
    c.setStrokeColor(NB_DIV)
    c.setLineWidth(0.8)
    c.line(dvx, nb_bot, dvx, kw_bot)
    c.setFillColor(NB_LBL)
    c.setFont(FONT_MAIN, 7.5)
    c.drawString(x0 + 4,  kw_bot - 12, 'CUES / KEYWORDS')
    c.drawString(dvx + 6, kw_bot - 12, 'NOTES')
    c.setStrokeColor(NB_BRD)
    c.setLineWidth(0.6)
    c.rect(x0, nb_bot, NB_CW, NB_NOTES_H, fill=0, stroke=1)
    # Summary area
    sb_bot = nb_bot - NB_SUM_H
    c.setFillColor(NB_SUMBG)
    c.rect(x0, sb_bot, NB_CW, NB_SUM_H, fill=1, stroke=0)
    c.setFillColor(NB_LBL)
    c.setFont(FONT_MAIN, 7.5)
    c.drawString(x0 + 4, nb_bot - 12, 'SUMMARY')
    c.setStrokeColor(NB_HLINE)
    c.setLineWidth(0.5)
    c.line(x0, nb_bot - 16, x0 + NB_CW, nb_bot - 16)
    c.setStrokeColor(NB_BRD)
    c.setLineWidth(0.6)
    c.rect(x0, sb_bot, NB_CW, NB_SUM_H, fill=0, stroke=1)
    return kw_bot, nb_bot


class _NbCtx:
    """State manager for Cornell Notes canvas rendering."""
    def __init__(self, c, subject: str, date_str: str):
        self.c        = c
        self.subject  = subject
        self.date_str = date_str
        self.page_num = 0
        self.cue_x = self.cue_w = 0
        self.ntx   = self.ntw   = 0
        self.ctop  = self.cbot  = 0
        self.stopy = 0
        self.cue_y = self.note_y = 0

    def begin(self, keywords=''):
        self.page_num += 1
        kw_bot, nb_bot = _nb_draw_page(
            self.c, self.page_num, self.subject, self.date_str, keywords)
        dvx          = NB_ML + NB_CUE_W
        self.cue_x   = NB_ML + 4
        self.cue_w   = NB_CUE_W - 10
        self.ntx     = dvx + 8
        self.ntw     = NB_COL_W - 14
        self.ctop    = kw_bot - 20
        self.cbot    = nb_bot + 4
        self.stopy   = nb_bot
        self.cue_y   = self.ctop
        self.note_y  = self.ctop

    def w(self, text, font, size, x, y, mw, color, indent=0):
        """Render CJK-wrapped text; return new y."""
        lns = _nb_split(text, font, size, mw - indent)
        self.c.setFont(font, size)
        self.c.setFillColor(color)
        for ln in lns:
            self.c.drawString(x + indent, y, ln)
            y -= NB_LINE_H
        return y

    def chk(self, kw=''):
        """Start a new page if notes column is nearly full."""
        if self.note_y < self.cbot + 16:
            self.c.showPage()
            self.begin(kw)

    def summary(self, text, color=None):
        """Write text in the SUMMARY area of the current page."""
        if not text:
            return
        color = color or NB_PHRASE
        y = self.stopy - 28
        lns = _nb_split(text, FONT_MAIN, 8.5, NB_CW - 12)
        self.c.setFont(FONT_MAIN, 8.5)
        self.c.setFillColor(color)
        for ln in lns:
            if y < self.stopy - NB_SUM_H + 4:
                break
            self.c.drawString(self.cue_x, y, ln)
            y -= NB_LINE_H


def _nb_item(ctx: '_NbCtx', item: dict, show_answers: bool):
    """Render one body/fill item onto the Cornell Notes canvas."""
    itype = item.get('type', 'body')
    text  = _normalize_blanks(item.get('text', ''))
    ans   = item.get('answer', '')
    if itype == 'body':
        ctx.note_y = ctx.w(text, FONT_LIGHT, 8.5, ctx.ntx, ctx.note_y, ctx.ntw, NB_TXT)
    elif itype == 'fill':
        ctx.note_y = ctx.w(text, FONT_MAIN, 9, ctx.ntx, ctx.note_y, ctx.ntw, NB_TXT, indent=4)
        if show_answers and ans:
            ctx.note_y = ctx.w(
                f'↳ {ans}', FONT_LIGHT, 8,
                ctx.ntx, ctx.note_y, ctx.ntw, NB_ANS, indent=12)
    ctx.note_y -= 2


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
