#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pdf_engine


DB_PATH = Path(os.environ.get("XR_SOURCE_DB", "/tmp/xingrun-prod-20260614-he-shujian.db"))
TEACHER_NAME = "何姝健"
DATE_START = "2026-06-13"
DATE_END_EXCLUSIVE = "2026-06-15"
OUTPUT_DIR = REPO_ROOT / "output" / "pdf" / "何姝健-6月13日6月14日错题练习分析引导版PDF-20260613-20260614"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images" / "original"
ZIP_PATH = OUTPUT_DIR.with_suffix(".zip")


GUIDE_OVERRIDES = {
    "wechat-362bfe365747971a": {
        "analysis_title": "等边综合题，先比差异再动手",
        "analysis": "这题虽然长得像课堂例题，但新条件集中在 H、G、中点和后面的 120 度角，不能直接套旧证明。先把等边三角形给出的 60 度和等边条件整理出来，再判断每一问到底要用全等、旋转还是中点关系。",
        "method_reminders": [
            "先圈出本题和例题不一样的条件，尤其是 H、G、中点和给定长度。",
            "等边三角形先转成三条边相等和三个 60 度角，再决定能不能用 SAS。",
        ],
        "guidance": [
            "第 1 问先比较 △ABD 和 △BCE，确认 AD=BE、AB=BC、夹角都是 60 度。",
            "第 2 问看到 G 是 BC 中点，不要急着算，先想中位线或倍长中线怎样把 AF 和 FG 联系起来。",
            "第 3 问先把 120 度、BM=BN、中点 H 标在图上，再找能把 PM 和 CN 放到同一组旋转或全等结构里的关系。",
        ],
        "redo_tip": "订正时先写“本题新增条件”清单，再开始证明，避免把课堂例题照搬一遍。",
    },
    "wechat-cfef67ab2cf9d033": {
        "analysis_title": "新定义题，入口是先展开前几项",
        "analysis": "这类题不是靠猜选项，而是先把定义翻译成可计算的式子。M0、M1、M2、M3、M4 要先按规则写出来，再看系数和 F(Mn) 到底取了哪些项。",
        "method_reminders": [
            "先照定义写 M0 到 M4，不要直接判断四个说法。",
            "系数和不是把题面所有 a 都相加，要看当前 Mn 里实际出现了哪些项。",
        ],
        "guidance": [
            "把 M0、M1、M2、M3、M4 各写一行，用颜色圈出真正留在式子里的项。",
            "判断 ①② 时直接代展开式，判断 ③④ 时先把 F(Mn) 的限制转成非负整数拆分。",
            "每判断一个说法，都在旁边写“用了定义哪一句”，不要凭感觉选个数。",
        ],
        "redo_tip": "订正时必须留下前四项展开式，这是新定义题最稳的起步。",
    },
    "wechat-c3d9666f6e7a2a2c": {
        "analysis_title": "折叠导角题，先把对应角列清楚",
        "analysis": "这题的难点不是图复杂，而是两次折叠后角会被搬来搬去。先把第一次折叠、第二次折叠分别带来的对应角相等写在图旁，再用 ∠CEF=2∠EBD' 建方程。",
        "method_reminders": [
            "每折一次，就把对应边、对应角单独列一组，不能混在一起倒角。",
            "设 ∠EBD' 为 x 后，再把 ∠CEF 和目标角都改写成 x 的关系。",
        ],
        "guidance": [
            "先标出长方形中的直角和折叠后重合的角。",
            "再用 ∠CEF=2∠EBD' 作为方程入口，把未知角统一成同一个字母。",
            "最后回到 A'D'、E'D'、EF 形成的角关系，检查有没有把内外角看反。",
        ],
        "redo_tip": "订正时按“第一次折叠、第二次折叠、题目给的倍角关系”三行来写。",
    },
    "wechat-e5b005d3db060704": {
        "analysis_title": "旋转翻折最值题，角度链不能跳",
        "analysis": "这题后半段把等边、旋转、翻折和最小值放在一起，真正要稳住的是角度链。先用等边和旋转找 60 度关系，再用翻折找对应角，最后才处理 PH+CP 的最小值。",
        "method_reminders": [
            "先区分旋转得到的角和翻折得到的角，不要把两类等角混用。",
            "遇到 PH+CP 最小值，要想办法把折线段转成一条直线段。",
        ],
        "guidance": [
            "第 1、2 问先把等边三角形和 60 度旋转能推出的全等关系写出来。",
            "第 3 问先设 ∠GCM=α，把 ∠BCG、∠MCP、∠GCP 逐个标出来。",
            "处理最小值时，先说明你做的是对称或旋转转化，再由直线最短回推 ∠CHP。",
        ],
        "redo_tip": "订正时不要只写最后角度式，必须保留“角从哪里来”的标注。",
    },
    "wechat-eb185b7cfac3bd77": {
        "analysis_title": "中点和 90 度条件要一起用",
        "analysis": "这题的入口在 H 是 BD 中点，以及 ∠ACB+∠D=90 度。单独看等腰或单独看角都不够，要把中点带来的线段转化和等腰三角形的角关系合在一起。",
        "method_reminders": [
            "先把 AB=AC、AE=AD 产生的等腰角标出来。",
            "看到 H 是 BD 中点，优先想中位线、倍长中线或构造与 AH 相关的线段。",
        ],
        "guidance": [
            "第 1 问先利用垂直平分线得到 EA=EB，再和 AB⊥AC、15 度角联系。",
            "第 2 问先从 ∠ACB+∠D=90 度推出可用的互余关系，再决定是否需要倍长 AH。",
            "目标 EC=2AH 里出现 2 倍，通常意味着中点构造或倍长线段，不要直接硬证。",
        ],
        "redo_tip": "订正时把“等腰给角、中点给倍长、互余给角关系”三类条件分栏写。",
    },
    "wechat-47938f30ffe08842": {
        "analysis_title": "等边模型先找全等，再用中点",
        "analysis": "这题不能只说不会。等边三角形已经给了边相等和 60 度，AD=BE 又把 D、E 两边拉到一起，第一问很适合先找全等；后面出现中点 G、H 时再转到中位线或倍长中线。",
        "method_reminders": [
            "等边三角形先写出 AB=BC=AC 和三个 60 度角。",
            "中点条件出现后，优先想中位线、倍长中线或把线段放进同一个三角形。",
        ],
        "guidance": [
            "先用 AD=BE 和等边条件尝试证明 △ABD≌△BCE。",
            "得到角关系后，再看 F、G、H 分别在第 2、3 问里承担什么功能。",
            "每问结束后检查：有没有把上一问结论带到下一问，而不是每问重新乱猜。",
        ],
        "redo_tip": "订正时把三问之间的可继承结论用箭头连起来。",
    },
    "wechat-e42ca199a6ade87d": {
        "analysis_title": "隔项递推要先写展开式",
        "analysis": "这题卡在定义理解。题面示例说明 M2 会接到 M0，所以要先看清递推到底隔了哪一项，再判断系数和。只看 a0、a1、a2 的字母顺序会很容易误选。",
        "method_reminders": [
            "先按题面示例写 M0、M1、M2、M3、M4，观察下标是怎样跳的。",
            "F(Mn) 只算当前整式里出现的系数，不能把没有出现的项算进去。",
        ],
        "guidance": [
            "先检查 ①：M4 里是否应该含有 a0，这一步能暴露递推是否读准。",
            "再用给定数值验证 ②，不要只凭 a0+a1+a2+a3 心算。",
            "③④ 涉及“所有满足条件”，要把正整数和非负整数的限制分开列。",
        ],
        "redo_tip": "订正时在每个选项旁写一行验证式，比只写正确个数更重要。",
    },
    "wechat-470351621746e0d3": {
        "analysis_title": "面积比例题，先把线段比转成面积比",
        "analysis": "这题给了 CD:BD=1:2 和 F 是 AD 中点，真正要做的是把这些线段比一步步转成三角形面积比。不要先猜总面积，先找同高三角形。",
        "method_reminders": [
            "先标 CD:BD=1:2、AF=FD，再找哪些三角形同高。",
            "面积比优先从同底或同高出发，不要直接套一个没说明来源的比例。",
        ],
        "guidance": [
            "从 △ABF 和 △BFD 入手，用 F 是中点建立面积相等。",
            "再用 CD:BD=1:2 把含 C、D、B 的面积关系接上。",
            "最后把已知 S△AEF=2 放进比例链，回到 S△ABC。",
        ],
        "redo_tip": "订正时每一步比例后面都写清楚“同高”或“同底”。",
    },
    "wechat-c7fa55d3a6d5cce9": {
        "analysis_title": "两次折叠要分层记录",
        "analysis": "这题要把折叠对称性和角度方程结合。先把沿 BE 折叠得到的关系写一层，再把沿 BD' 折叠得到的关系写一层，最后再处理 ∠CEF=2∠EBD'。",
        "method_reminders": [
            "先列折叠对应角，再列题目给的倍角关系。",
            "设未知角以后，所有目标角都尽量改写成同一个未知数。",
        ],
        "guidance": [
            "把点 A、D、E 折到 A'、D'、E' 后，对应的角相等关系逐个标图。",
            "用 ∠CEF=2∠EBD' 建立关键方程，别直接猜 ∠E'D'F。",
            "求出角以后，回图检查 F 点在延长线上带来的外角方向。",
        ],
        "redo_tip": "订正时把“折叠 1 / 折叠 2 / 倍角条件”分三段写，别混成一串。",
    },
    "wechat-e7dbc468b7e7a634": {
        "analysis_title": "角平分线遇到对角互补，要先转角",
        "analysis": "∠A+∠C=180 度不是普通补角，它常提示四点共圆或外角等于内对角。BD 平分 ∠ABC 后，目标 DC=AD 可以通过等角推出等边，也可以借助辅助线构造全等。",
        "method_reminders": [
            "先把 ∠A+∠C=180 度转成可用的圆内接四边形角关系。",
            "BD 平分角要立刻写成 ∠ABD=∠DBC，再看这两个角能转到哪里。",
        ],
        "guidance": [
            "先判断能否把 A、B、C、D 放到同一个圆上，写出外角或同弧角关系。",
            "把 ∠ABD=∠DBC 通过圆或三角形角关系转到 △ADC 中。",
            "当 △ADC 出现两个底角相等时，再落到 DC=AD。",
        ],
        "redo_tip": "订正时先写角关系链，再写等边结论，别一上来画线硬证。",
    },
    "wechat-5c7d804bfb5a55ef": {
        "analysis_title": "配套问题先写数量，再写比例",
        "analysis": "这题的核心是“刚好完全配套”。设 x 天生产螺母，就要分别写出螺母总数和螺丝总数，再按每个零件需要 5 个螺丝、3 个螺母建立比例。",
        "method_reminders": [
            "x 天生产螺母，所以螺母数量是 90x，螺丝生产天数是 12-x。",
            "配套关系不是数量相等，而是螺丝:螺母=5:3。",
        ],
        "guidance": [
            "先写螺母总数：90x，再写螺丝总数：150(12-x)。",
            "根据 5 个螺丝配 3 个螺母，把两个总量交叉相乘。",
            "最后对照四个选项，看哪一个表示的是同一个配套比例。",
        ],
        "redo_tip": "订正时在方程前先写“螺丝数”和“螺母数”，不要直接选式子。",
    },
    "wechat-153bcdb24f77b4aa": {
        "analysis_title": "几何概率先算面积比",
        "analysis": "随机停在三角形内，概率就是阴影面积除以三角形总面积。这里要先认出总区域是等腰直角三角形，阴影区域和以 B 为圆心、半径 2 的扇形有关。",
        "method_reminders": [
            "先算总面积 S△ABC，再判断阴影部分是什么扇形或组合图形。",
            "扇形面积用 圆心角/360 × πr²，圆心角要从等腰直角三角形里找。",
        ],
        "guidance": [
            "先由 AB=AC=2、∠A=90 度求三角形面积。",
            "再确定弧 BD 对应的圆心角，半径是 AB。",
            "最后用 阴影面积/总面积 写概率，别把长度比当成概率。",
        ],
        "redo_tip": "订正时画出总区域和所求区域，面积公式写在图旁边。",
    },
    "wechat-82d56823d4264b49": {
        "analysis_title": "无数解要化成 0x=0",
        "analysis": "含参一元一次方程有无数个解，关键不是把 x 随便约掉，而是整理后未知数系数为 0、常数项也为 0。两个条件必须同时成立。",
        "method_reminders": [
            "先把含 x 的项移到一边，常数项移到另一边。",
            "无数解对应 0·x=0，所以 x 的系数和常数差都要为 0。",
        ],
        "guidance": [
            "把 m/3 x 和 x/3 合并，得到关于 x 的系数条件。",
            "再比较常数 1 和 n/2，得到常数条件。",
            "求出 m、n 后再算 m+n，检查不是只满足其中一个条件。",
        ],
        "redo_tip": "订正时写出“唯一解 / 无解 / 无数解”的判定表，再代本题。",
    },
    "wechat-691d2d80a09e7b94": {
        "analysis_title": "角平分线和面积比要接起来",
        "analysis": "这题给了 CD=2BD、4BC=3AC 和角平分线 CF，目标是阴影四边形面积。要先用线段比例建立面积比例，再用角平分线把 AB 上的分点关系接进来。",
        "method_reminders": [
            "先把 CD:BD 和 AC:BC 写成比例，不要直接算阴影。",
            "角平分线进入三角形后，要想到分边比例和等高面积比。",
        ],
        "guidance": [
            "从 △CDE 的面积 7 出发，用 CD:BD 推出与同高三角形相关的面积。",
            "再利用 4BC=3AC 和 CF 平分角，确定 F 在 AB 上的比例关系。",
            "最后把 BDEF 看成由几个小三角形拼出来，逐块相加或相减。",
        ],
        "redo_tip": "订正时先画面积分块图，再列比例，不要只写一个结果。",
    },
    "wechat-7e65eafabc82cd9c": {
        "analysis_title": "复杂几何先拆条件，不要从结论硬推",
        "analysis": "这题和前面的中点等腰综合类似，条件多但入口清楚：垂直平分线给相等，中点 H 给倍长或中位线，等腰三角形给角关系。先拆条件，再去看目标 DE 或 EC=2AH。",
        "method_reminders": [
            "垂直平分线先转成到 A、B 两点距离相等。",
            "看到 EC=2AH 这种 2 倍目标，要优先考虑中点构造或倍长 AH。",
        ],
        "guidance": [
            "第 1 问先利用 FE 垂直平分 AB 得到 EA=EB，再结合 AB⊥AC 和 15 度角导出所需线段。",
            "第 2 问把 AB=AC、AE=AD 的等腰角分别标出来。",
            "再用 H 是 BD 中点构造与 AH 等长或 2AH 相关的线段，服务 EC=2AH。",
        ],
        "redo_tip": "订正时每个已知条件至少写一次用途，防止只抄题不推理。",
    },
    "wechat-943c464fc51d6664": {
        "analysis_title": "等边旋转和将军饮马要分两步",
        "analysis": "这题综合度高，不能把最值问题和旋转全等混在一起。先用等边三角形的 60 度旋转解决数量关系，再在第三问里把 PH+CP 的最小值转成直线最短。",
        "method_reminders": [
            "等边三角形中的旋转通常服务于构造全等和转移线段。",
            "线段和最小值要想到对称或旋转，把折线转成直线。",
        ],
        "guidance": [
            "第 1 问先用垂直和等边三角形求出关键直角三角形关系。",
            "第 2 问明确 CD 绕 C 旋转 60 度到 CF 后，哪些边和角可对应。",
            "第 3 问先处理翻折得到的角，再用最短路径思想确定 M 的特殊位置。",
        ],
        "redo_tip": "订正时把“旋转全等”和“最短路径”分成两个小标题写。",
    },
}


def sanitize_filename(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "-", value).strip()


def date_label(value: str) -> str:
    return f"{int(value[5:7])}月{int(value[8:10])}日"


def date_range_label(dates: list[str]) -> str:
    if not dates:
        return "6月13日6月14日"
    if len(dates) == 1:
        return date_label(dates[0])
    return "".join(date_label(value) for value in dates)


def normalize_math_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\r", "\n")
    text = text.replace("$$", "")
    text = text.replace("$", "")
    replacements = {
        "\\triangle": "△",
        "\\angle": "∠",
        "\\parallel": "∥",
        "\\perp": "⊥",
        "\\cdots": "…",
        "\\ldots": "…",
        "\\alpha": "α",
        "\\quad": " ",
        "\\qquad": " ",
        "\\circ": "°",
        "^\\circ": "°",
        "\\times": "×",
        "\\cdot": "·",
        "\\leq": "≤",
        "\\geq": "≥",
        "\\neq": "≠",
        "\\text": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\underline\{[^{}]*\}", "______", text)
    text = text.replace("^°", "°")
    text = text.replace("{", "").replace("}", "")
    text = text.replace("\\ ", " ")
    text = text.replace("\\", "")
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compact_text(text: str) -> str:
    return " ".join(normalize_math_text(text).replace("\n", " ").split())


def fetch_rows() -> list[dict]:
    if not DB_PATH.exists():
        raise SystemExit(f"Source DB not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            select
              t.id as task_id,
              t.created_at as upload_created_at,
              t.updated_at as task_updated_at,
              t.status as task_status,
              t.error_message,
              t.record_id,
              t.image_url as task_image_url,
              u.id as teacher_id,
              u.display_name as teacher_name,
              c.id as class_id,
              c.name as class_name,
              s.id as student_id,
              s.name as student_name,
              w.image_url,
              w.primary_error_type,
              w.secondary_error_summary,
              w.child_reason_core_issue,
              w.child_reason_key_omission,
              w.child_reason_next_step,
              w.child_reason_transcript,
              w.child_raw_reason_text,
              w.topic_category,
              w.recognition_status,
              w.archive_status,
              w.image_rotation_degrees,
              w.question_text
            from wechat_wrong_question_upload_tasks t
            join wrong_question_submissions w on w.id = t.record_id
            join users u on u.id = t.teacher_user_id
            join classes c on c.id = t.class_id
            join students s on s.id = t.student_id
            where u.display_name = ?
              and t.created_at >= ?
              and t.created_at < ?
              and t.status = 'ready'
              and w.recognition_status = 'recognized'
              and w.archive_status = 'active'
            order by t.created_at, t.id
            """,
            (TEACHER_NAME, f"{DATE_START} 00:00:00", f"{DATE_END_EXCLUSIVE} 00:00:00"),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def wrap_lines(pdf: canvas.Canvas, text: str, font_name: str, font_size: float, max_width: float, max_lines: int | None = None) -> list[str]:
    normalized = compact_text(text)
    if not normalized:
        return []
    lines: list[str] = []
    current = ""
    for char in normalized:
        trial = current + char
        if pdf.stringWidth(trial, font_name, font_size) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = char
        if max_lines and len(lines) >= max_lines:
            break
    if (not max_lines or len(lines) < max_lines) and current:
        lines.append(current)
    if max_lines and len(lines) >= max_lines and len("".join(lines)) < len(normalized):
        lines[-1] = lines[-1].rstrip("，。；,. ") + "…"
    return lines


def draw_text_lines(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    top_y: float,
    width: float,
    font_name: str,
    font_size: float,
    line_gap: float,
    color: colors.Color,
    max_lines: int | None = None,
) -> float:
    pdf.setFillColor(color)
    pdf.setFont(font_name, font_size)
    y = top_y
    for line in wrap_lines(pdf, text, font_name, font_size, width, max_lines=max_lines):
        pdf.drawString(x, y, line)
        y -= line_gap
    return y


def draw_box(pdf: canvas.Canvas, x: float, bottom: float, width: float, height: float, fill: str, stroke: str) -> None:
    pdf.setStrokeColor(colors.HexColor(stroke))
    pdf.setFillColor(colors.HexColor(fill))
    pdf.roundRect(x, bottom, width, height, 3 * mm, stroke=1, fill=1)


def draw_box_title(pdf: canvas.Canvas, title: str, x: float, y: float, font_name: str) -> None:
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.setFont(font_name, 11.5)
    pdf.drawString(x, y, title)


def download_image(url: str, destination: Path, rotation_degrees: int = 0) -> tuple[int, int]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    image = Image.open(BytesIO(raw))
    image = ImageOps.exif_transpose(image)
    if rotation_degrees in {90, 180, 270}:
        image = image.rotate(-rotation_degrees, expand=True)
    image.load()
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return image.size


def prepare_items(rows: list[dict]) -> list[dict]:
    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for index, row in enumerate(rows, start=1):
        record_id = row["record_id"]
        guide = GUIDE_OVERRIDES.get(record_id)
        if not guide:
            raise SystemExit(f"Missing guide override for {record_id}")
        suffix = Path(urllib.parse.urlparse(row["image_url"]).path).suffix or ".jpg"
        image_path = OUTPUT_IMAGES_DIR / f"{index:02d}-{record_id}{suffix}"
        size = download_image(row["image_url"], image_path, int(row["image_rotation_degrees"] or 0))
        item = dict(row)
        item["question_text_clean"] = normalize_math_text(row["question_text"])
        item["image_local_path"] = str(image_path)
        item["image_size"] = size
        item.update(guide)
        items.append(item)
    return items


def draw_question_page(pdf: canvas.Canvas, item: dict, question_order: int, font_name: str) -> None:
    page_width, page_height = A4
    margin_x = 13.5 * mm
    top_y = page_height - 13 * mm
    bottom_margin = 11 * mm
    content_width = page_width - margin_x * 2

    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.setFont(font_name, 17)
    pdf.drawString(margin_x, top_y, f"第 {question_order} 题")

    pdf.setFont(font_name, 9.5)
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.drawString(margin_x, top_y - 7 * mm, "原题 / 原图 + 分析引导练习")
    pdf.drawRightString(page_width - margin_x, top_y - 7 * mm, f"上传时间：{item['upload_created_at']}")

    image_top = top_y - 12 * mm
    image_height = 56 * mm
    image_bottom = image_top - image_height
    draw_box(pdf, margin_x, image_bottom, content_width, image_height, "#f8fafc", "#dbe3ee")

    image = Image.open(item["image_local_path"])
    image = ImageOps.exif_transpose(image)
    image_width, image_height_px = image.size
    ratio = min((content_width - 10 * mm) / image_width, (image_height - 8 * mm) / image_height_px)
    draw_width = image_width * ratio
    draw_height = image_height_px * ratio
    draw_x = margin_x + (content_width - draw_width) / 2
    draw_y = image_bottom + (image_height - draw_height) / 2
    pdf.drawImage(ImageReader(image), draw_x, draw_y, width=draw_width, height=draw_height, preserveAspectRatio=True, mask="auto")

    question_top = image_bottom - 5 * mm
    question_height = 20 * mm
    draw_box(pdf, margin_x, question_top - question_height, content_width, question_height, "#ffffff", "#dbe3ee")
    draw_box_title(pdf, "题干提炼", margin_x + 4 * mm, question_top - 5 * mm, font_name)
    draw_text_lines(
        pdf,
        item["question_text_clean"],
        margin_x + 4 * mm,
        question_top - 10 * mm,
        content_width - 8 * mm,
        font_name,
        7.8,
        3.8 * mm,
        colors.HexColor("#334155"),
        max_lines=3,
    )

    analysis_top = question_top - question_height - 4.5 * mm
    analysis_height = 25 * mm
    draw_box(pdf, margin_x, analysis_top - analysis_height, content_width, analysis_height, "#f8fafc", "#cbd5e1")
    draw_box_title(pdf, f"题目分析｜{item['analysis_title']}", margin_x + 4 * mm, analysis_top - 5 * mm, font_name)
    analysis_text = item["analysis"]
    if item.get("secondary_error_summary"):
        analysis_text += f" 当前卡点：{item['secondary_error_summary']}"
    draw_text_lines(
        pdf,
        analysis_text,
        margin_x + 4 * mm,
        analysis_top - 10 * mm,
        content_width - 8 * mm,
        font_name,
        8.0,
        4.0 * mm,
        colors.HexColor("#334155"),
        max_lines=4,
    )

    reminder_top = analysis_top - analysis_height - 4.5 * mm
    reminder_height = 21 * mm
    draw_box(pdf, margin_x, reminder_top - reminder_height, content_width, reminder_height, "#fff7ed", "#fed7aa")
    draw_box_title(pdf, "方法提醒", margin_x + 4 * mm, reminder_top - 5 * mm, font_name)
    reminder_y = reminder_top - 10 * mm
    for reminder in item["method_reminders"]:
        reminder_y = draw_text_lines(
            pdf,
            reminder,
            margin_x + 4 * mm,
            reminder_y,
            content_width - 8 * mm,
            font_name,
            8.1,
            4.1 * mm,
            colors.HexColor("#9a3412"),
            max_lines=1,
        ) - 0.5 * mm

    guide_top = reminder_top - reminder_height - 4.5 * mm
    guide_height = 35 * mm
    draw_box(pdf, margin_x, guide_top - guide_height, content_width, guide_height, "#eff6ff", "#bfdbfe")
    draw_box_title(pdf, "做法引导", margin_x + 4 * mm, guide_top - 5 * mm, font_name)
    current_y = guide_top - 10 * mm
    for index, prompt in enumerate(item["guidance"], start=1):
        current_y = draw_text_lines(
            pdf,
            f"{index}. {prompt}",
            margin_x + 4 * mm,
            current_y,
            content_width - 8 * mm,
            font_name,
            8.0,
            4.0 * mm,
            colors.HexColor("#1e3a8a"),
            max_lines=1,
        ) - 0.3 * mm
    draw_text_lines(
        pdf,
        f"落笔提醒：{item['redo_tip']}",
        margin_x + 4 * mm,
        current_y,
        content_width - 8 * mm,
        font_name,
        7.8,
        3.8 * mm,
        colors.HexColor("#475569"),
        max_lines=1,
    )

    redo_top = guide_top - guide_height - 4.5 * mm
    redo_bottom = bottom_margin
    redo_height = redo_top - redo_bottom
    draw_box(pdf, margin_x, redo_bottom, content_width, redo_height, "#ffffff", "#dbe3ee")
    draw_box_title(pdf, "订正区", margin_x + 4 * mm, redo_top - 5 * mm, font_name)
    for line_index in range(5):
        y = redo_top - 11 * mm - line_index * 7.0 * mm
        if y <= redo_bottom + 7 * mm:
            break
        pdf.setStrokeColor(colors.HexColor("#cbd5e1"))
        pdf.line(margin_x + 4 * mm, y, page_width - margin_x - 4 * mm, y)

    footer = f"来源记录：{item['record_id']}｜任务状态：{item['task_status']}｜错因：{item['primary_error_type'] or '待补充'}"
    pdf.setFont(font_name, 7.3)
    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.drawString(margin_x + 4 * mm, redo_bottom + 3.4 * mm, footer)


def render_student_pdf(student_items: list[dict], pdf_path: Path) -> None:
    pdf_engine._ensure_fonts()
    try:
        pdfmetrics.getFont(pdf_engine.FONT_MAIN)
        font_name = pdf_engine.FONT_MAIN
    except KeyError:
        font_name = "Helvetica"

    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    pdf.setTitle(pdf_path.stem)
    for index, item in enumerate(student_items, start=1):
        draw_question_page(pdf, item, index, font_name)
        pdf.showPage()
    pdf.save()


def write_metadata(items: list[dict], pdf_records: list[dict]) -> Path:
    counts_by_student = defaultdict(int)
    counts_by_day = defaultdict(int)
    for item in items:
        counts_by_student[item["student_name"]] += 1
        counts_by_day[item["upload_created_at"][:10]] += 1
    metadata = {
        "teacher_name": TEACHER_NAME,
        "date_start": DATE_START,
        "date_end_exclusive": DATE_END_EXCLUSIVE,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_db": str(DB_PATH),
        "output_dir": str(OUTPUT_DIR),
        "zip_path": str(ZIP_PATH),
        "layout": "original-image-analysis-method-reminder-guidance-redo",
        "total_question_count": len(items),
        "student_counts": dict(sorted(counts_by_student.items())),
        "day_counts": dict(sorted(counts_by_day.items())),
        "pdfs": pdf_records,
        "items": [
            {
                "task_id": item["task_id"],
                "record_id": item["record_id"],
                "student_id": item["student_id"],
                "student_name": item["student_name"],
                "class_id": item["class_id"],
                "class_name": item["class_name"],
                "created_at": item["upload_created_at"],
                "task_status": item["task_status"],
                "recognition_status": item["recognition_status"],
                "archive_status": item["archive_status"],
                "primary_error_type": item["primary_error_type"],
                "secondary_error_summary": item["secondary_error_summary"],
                "image_url": item["image_url"],
                "local_image_path": item["image_local_path"],
                "image_size": item["image_size"],
                "question_text": item["question_text_clean"],
                "analysis_title": item["analysis_title"],
                "analysis": item["analysis"],
                "method_reminders": item["method_reminders"],
                "guidance": item["guidance"],
                "redo_tip": item["redo_tip"],
            }
            for item in items
        ],
    }
    metadata_path = OUTPUT_DIR / "generation-metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_path


def write_zip(pdf_records: list[dict], metadata_path: Path) -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with ZipFile(ZIP_PATH, "w", ZIP_DEFLATED) as archive:
        for record in pdf_records:
            pdf_path = Path(record["pdf_path"])
            archive.write(pdf_path, arcname=pdf_path.name)
        archive.write(metadata_path, arcname=metadata_path.name)
        for path in sorted(OUTPUT_IMAGES_DIR.glob("*")):
            archive.write(path, arcname=f"images/original/{path.name}")


def main() -> None:
    rows = fetch_rows()
    if len(rows) != 16:
        raise SystemExit(f"Expected 16 usable rows, got {len(rows)}")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    items = prepare_items(rows)
    students: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for item in items:
        students[(int(item["student_id"]), item["student_name"])].append(item)

    pdf_records: list[dict] = []
    for (_student_id, student_name), student_items in sorted(students.items(), key=lambda pair: (pair[1][0]["class_name"], pair[0][1])):
        dates = sorted({item["upload_created_at"][:10] for item in student_items})
        label = date_range_label(dates)
        date_start = dates[0].replace("-", "")
        date_end = dates[-1].replace("-", "")
        class_name = student_items[0]["class_name"]
        pdf_name = sanitize_filename(f"{class_name}-{student_name}-{label}错题练习分析引导版-{date_start}-{date_end}.pdf")
        pdf_path = OUTPUT_DIR / pdf_name
        render_student_pdf(student_items, pdf_path)
        pdf_records.append(
            {
                "student_name": student_name,
                "class_name": class_name,
                "question_count": len(student_items),
                "dates": dates,
                "pdf_path": str(pdf_path),
            }
        )

    metadata_path = write_metadata(items, pdf_records)
    write_zip(pdf_records, metadata_path)
    print(metadata_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
