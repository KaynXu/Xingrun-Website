#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 处理模块：
  - 音频转录（faster-whisper）
  - 课堂总结解析 → 结构化复习计划 JSON（DeepSeek）
  - 月度复习计划聚合
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import date
from config_runtime import get_runtime_config
from lesson_manager import CONSULTATION_FOLLOW_UP_STATUS_OPTIONS

# ─── 配置加载 ──────────────────────────────────────────────────────────────────
def _load_config() -> dict:
  return get_runtime_config()


def _provider_name() -> str:
    return str(_load_config().get("provider", "deepseek") or "deepseek")


def _usage_dict(response, *, provider: str | None = None, model_fallback: str = "") -> dict:
    usage = getattr(response, "usage", None)
    return {
        "provider": str(provider or _provider_name()),
        "model": str(getattr(response, "model", "") or model_fallback or _get_chat_model()),
        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }


def _get_client():
    """返回当前配置的 AI 服务商客户端（兼容 OpenAI SDK）。"""
    from openai import OpenAI
    cfg = _load_config()
    provider = cfg.get("provider", "deepseek")

    if provider == "deepseek":
        key = cfg.get("deepseek_api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise RuntimeError("未找到 DeepSeek API Key，请在设置页面配置。")
        return OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")

    elif provider == "mimo":
        key = cfg.get("mimo_api_key", "") or os.environ.get("MIMO_API_KEY", "")
        base_url = cfg.get("mimo_base_url", "").strip()
        if not key:
            raise RuntimeError("未找到 MiMo API Key，请在设置页面配置。")
        if not base_url:
            raise RuntimeError("未配置 MiMo Base URL，请在设置页面填写接口地址。")
        return OpenAI(api_key=key, base_url=base_url)

    else:  # openai（默认）
        key = cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError(
                "未找到 OpenAI API Key。\n"
                "请在设置页面配置 openai_api_key，"
                "或设置环境变量 OPENAI_API_KEY。"
            )
        return OpenAI(api_key=key)


def _get_vision_client():
    from openai import OpenAI
    cfg = _load_config()
    provider = str(cfg.get("vision_provider") or "qwen").strip() or "qwen"

    if provider == "openai":
        key = cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("未找到 OpenAI API Key，请在设置页面配置。")
        return OpenAI(api_key=key)

    if provider == "mimo":
        key = cfg.get("mimo_api_key", "") or os.environ.get("MIMO_API_KEY", "")
        base_url = cfg.get("mimo_base_url", "").strip()
        if not key:
            raise RuntimeError("未找到 MiMo API Key，请在设置页面配置。")
        if not base_url:
            raise RuntimeError("未配置 MiMo Base URL，请在设置页面填写接口地址。")
        return OpenAI(api_key=key, base_url=base_url)

    if provider == "qwen":
        key = cfg.get("qwen_api_key", "") or os.environ.get("DASHSCOPE_API_KEY", "")
        base_url = cfg.get("qwen_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
        if not key:
            raise RuntimeError("未找到 DashScope API Key，请配置 DASHSCOPE_API_KEY。")
        return OpenAI(api_key=key, base_url=base_url)

    return _get_client()


def _get_chat_model() -> str:
    """返回当前服务商对应的对话模型名称。"""
    cfg = _load_config()
    provider = cfg.get("provider", "deepseek")
    if provider == "deepseek":
        return cfg.get("deepseek_model", "deepseek-v4-pro")
    elif provider == "mimo":
        return cfg.get("mimo_model", "MiMo-7B-RL")
    return "gpt-4o"


def _get_structured_generation_model() -> str:
    return str(_get_chat_model() or "deepseek-v4-pro")


def _get_vision_model() -> str:
    return str(_load_config().get("vision_model") or "qwen-vl-max-latest")


_BARE_LATEX_COMMAND_RE = re.compile(
    r"(?<!\\)\\(?:left|right|frac|sqrt|theta|alpha|beta|gamma|delta|pi|sin|cos|tan|"
    r"log|ln|angle|parallel|perp|cdot|times|div|leq|geq|neq|pm|circ|text|overline|widehat)\b"
)


def _escape_bare_backslashes_in_json_strings(raw: str) -> str:
    result: list[str] = []
    in_string = False
    i = 0
    valid_simple_escapes = {'"', "\\", "/", "b", "f", "n", "r", "t"}

    while i < len(raw):
        char = raw[i]
        if not in_string:
            result.append(char)
            if char == '"':
                in_string = True
            i += 1
            continue

        if char == '"':
            result.append(char)
            in_string = False
            i += 1
            continue

        if char != "\\":
            result.append(char)
            i += 1
            continue

        if i + 1 >= len(raw):
            result.append("\\\\")
            i += 1
            continue

        next_char = raw[i + 1]
        if next_char == "u" and i + 5 < len(raw) and re.fullmatch(r"[0-9a-fA-F]{4}", raw[i + 2 : i + 6]):
            result.append(raw[i : i + 6])
            i += 6
            continue
        if next_char in {'"', "\\", "/"}:
            result.append(raw[i : i + 2])
            i += 2
            continue
        if next_char in valid_simple_escapes and not (i + 2 < len(raw) and raw[i + 2].isalpha()):
            result.append(raw[i : i + 2])
            i += 2
            continue

        result.append("\\\\")
        i += 1

    return "".join(result)


def _loads_model_json(raw: str | None, default: str = "{}"):
    content = raw if raw is not None and str(raw).strip() else default
    if _BARE_LATEX_COMMAND_RE.search(content):
        return json.loads(_escape_bare_backslashes_in_json_strings(content))
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return json.loads(_escape_bare_backslashes_in_json_strings(content))


_LOCAL_WHISPER_MODEL = None
_LOCAL_WHISPER_MODEL_LOCK = threading.Lock()
_LOCAL_WHISPER_MODEL_NAME = "base"


def _get_local_whisper_model_source() -> str:
    repo_dir = (
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / f"models--Systran--faster-whisper-{_LOCAL_WHISPER_MODEL_NAME}"
    )
    ref_path = repo_dir / "refs" / "main"
    if not ref_path.exists():
        return _LOCAL_WHISPER_MODEL_NAME
    revision = ref_path.read_text(encoding="utf-8").strip()
    if not revision:
        return _LOCAL_WHISPER_MODEL_NAME
    snapshot_dir = repo_dir / "snapshots" / revision
    if not snapshot_dir.exists():
        return _LOCAL_WHISPER_MODEL_NAME
    return str(snapshot_dir)


def _get_local_whisper_model():
    global _LOCAL_WHISPER_MODEL
    if _LOCAL_WHISPER_MODEL is not None:
        return _LOCAL_WHISPER_MODEL

    with _LOCAL_WHISPER_MODEL_LOCK:
        if _LOCAL_WHISPER_MODEL is not None:
            return _LOCAL_WHISPER_MODEL
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("未安装 faster-whisper，请先安装最新依赖。") from exc
        _LOCAL_WHISPER_MODEL = WhisperModel(
            _get_local_whisper_model_source(),
            device="cpu",
            compute_type="int8",
        )
        return _LOCAL_WHISPER_MODEL


def _local_whisper_usage_dict() -> dict:
    return {
        "provider": "local",
        "model": f"faster-whisper-{_LOCAL_WHISPER_MODEL_NAME}",
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _collect_local_transcript_text(segments) -> str:
    return "".join(str(getattr(segment, "text", "") or "") for segment in segments).strip()


def _transcribe_audio_path_locally(audio_path: str) -> str:
    model = _get_local_whisper_model()
    segments, _ = model.transcribe(
        str(audio_path),
        task="transcribe",
        vad_filter=True,
    )
    transcript_text = _collect_local_transcript_text(segments)
    if transcript_text:
        return transcript_text

    segments, _ = model.transcribe(
        str(audio_path),
        language="zh",
        task="transcribe",
        vad_filter=True,
    )
    transcript_text = _collect_local_transcript_text(segments)
    if not transcript_text:
        raise ValueError("audio transcription failed")
    return transcript_text


WRONG_QUESTION_RECOGNITION_PROMPT = """你是错题识别助手。
你需要判断上传图片是否属于几何题或几何体题，并提取可直接进入错题库的题目文本；如果题目依赖几何图、函数图、数轴或线段示意图，还要输出可重绘的结构化图像信息。
识别前必须先根据印刷文字、页边和题目排版判断图片正确阅读方向；如果原图是横着或倒着的，仍按旋正后的方向理解题目。
题目文本允许“正文 + LaTeX 公式”混合输出：
- 普通中文、英文和题干说明直接输出为普通文本
- 行内公式使用 $...$
- 独立成行的公式使用 $$...$$
- 在 JSON 字符串里，LaTeX 命令的反斜杠必须写成双反斜杠，例如 \\frac、\\text、\\to
- 不要把整道题都改写成纯 LaTeX，只把公式片段转成 LaTeX
如果能明确识别公式结构，优先输出可渲染的 LaTeX；如果某个符号拿不准，宁可保留原始可读文本，也不要编造错误公式。
如果题目里包含数轴、表格、函数图像、线段示意图、几何图形或其他辅助图，题目文本必须保留题干主体，并用自然语言补足解题所需的图中信息，不要只写“如图所示”。例如数轴图要说明点的位置关系、已标出的坐标或距离，如“图中 A 在 B 左侧”。
图像可重绘时，必须输出 diagram_type 与 diagram_spec：
- diagram_type 只能取 none、number_line、geometry、function_plot 之一。
- diagram_spec 为 JSON object；无法可靠重绘时返回 null。
- number_line 使用 {"type":"number_line","points":[{"label":"A","value":-5},{"label":"B","value":15}]}。
- geometry 使用 {"type":"geometry","points":[{"label":"A","x":0,"y":1}],"segments":[{"from":"A","to":"B"},{"from":"O","to":"D","dashed":true}]}，只记录题目图里解题必需的点、线、虚线和标注。
- function_plot 使用 {"type":"function_plot","x_min":-2,"x_max":2,"y_min":-1,"y_max":4,"curves":[{"label":"y=x^2","points":[[-2,4],[-1,1],[0,0],[1,1],[2,4]]}]}，用足够采样点表达函数走势和关键交点。
如果收到上一版审稿意见要求重新识别，必须逐条修正审稿指出的问题，尤其是题干原句、图中关键信息和问题问法；不要重复输出已被指出有误的文本。
只返回 JSON，不要输出额外解释。
返回字段必须包含：
- is_geometry: boolean
- question_text: string
- confidence: string
- notes: string
- image_rotation_degrees: number，只能是 0、90、180、270，表示为了让原始上传图片变成可阅读方向，需要顺时针旋转多少度
- diagram_type: string
- diagram_spec: object 或 null
如果是几何题，也要尽量返回题目文字和可重绘的 diagram_spec；只有题干文字无法可靠识别时，question_text 才返回空字符串。
如果不是几何题但无法可靠识别题目文本，也要如实返回空字符串，并在 notes 里说明原因。"""

WRONG_QUESTION_RECOGNITION_REVIEW_PROMPT = """你是错题识别质量审稿员。
你会收到原始错题图片、当前识别出的题目文本，以及可选的 LaTeX 渲染错误。
请判断这份题目文本是否适合直接进入学生错题库 PDF。

检查标准：
1. 只保留原始题目主体，不要包含学生手写答案、草稿、订正、批改痕迹、圈画说明或解题过程。
2. 不要漏掉原题关键条件、选项、问题问法。
3. 普通文字保留自然文本，不要整段改写成 LaTeX。
4. 行内短公式必须用 $...$。
5. 独立成行、较长公式、方程组、分段式、长根式或多行表达式必须用 $$...$$。
6. LaTeX 必须适合 KaTeX 渲染。
7. 如果图片里有数轴、表格、函数图像或线段示意图，只要题目文本已经用文字补足关键位置关系、数值、标注和问法，不要因为没有重绘原图而直接判不通过。

请用纯文本返回，不要返回 JSON。
第一行必须是“结论：通过”或“结论：不通过”。
如果不通过，后续先写“致命问题：”，只列会导致题目无法独立解答、条件错误、问法遗漏、混入学生痕迹或 LaTeX 不可渲染的问题；再写“可优化建议：”，列不影响入库使用的表达优化。只有存在致命问题时才判不通过。"""

_WRONG_QUESTION_RECOGNITION_MAX_ATTEMPTS = 3

WRONG_QUESTION_ERROR_TYPE_OPTIONS = [
    "知识点问题",
    "细节问题",
    "方法问题",
    "审题问题",
]

WRONG_QUESTION_REASON_CLASSIFICATION_PROMPT = """你是错因分析助手。
你会收到孩子自己描述“为什么错”，以及可选的题目文本。
你必须先把孩子的描述归类到以下固定顶层分类之一，再结合题目文本整理出老师和孩子都能直接使用的结构化错因分析：
- 知识点问题
- 细节问题
- 方法问题
- 审题问题

只返回 JSON，不要输出额外解释。
返回字段必须包含：
- display_text: string，老师可直接阅读的自然中文，概括孩子出错的核心原因，删除口头禅和无效内容，20 到 60 个字
- primary_error_type: string，且必须是以上固定分类之一
- secondary_error_summary: string，补充细节备注，允许出现单位、符号、书写、漏条件等具体表现，不要复述顶层分类名称，18 到 40 个字
- core_issue: string，核心错因，必须结合本题说清“错在什么理解、判断或步骤上”，40 到 90 个字
- key_omission: string，关键遗漏，说明孩子没有抓住的条件、定义、限制、检查动作或题目要求，40 到 90 个字
- next_step: string，后续操作，写成下次做同类题可执行的 1 到 2 步提醒，40 到 90 个字

规则：
- 优先依据孩子自己的描述归类，不要编造不存在的学习问题
- 如果孩子描述太模糊，也要结合题目文本给出最稳妥的分析，但必须用“可能”“需要检查”这类谨慎表述
- display_text 不得使用清洗后、原始转写等工程词汇"""

WRONG_QUESTION_PRACTICE_SHEET_PROMPT = """你是错题练习设计助手。
你会收到某个学生的一组错题快照，请为每道错题生成一份可直接印到 PDF 上的反思练习材料。

只返回 JSON，不要输出额外解释。
返回字段必须包含：
- title: string，整份练习单标题
- items: array，长度必须与输入题目数量一致，顺序必须与输入一致

items 中每一项必须包含：
- wrong_question_record_id: string，必须与输入题目里的 wrong_question_record_id 完全一致
- reason_blank_prompt: string，用于第一个书写区。请写成多行字符串：第一行是这个书写区的小标题；后续内容必须是简短挖空题正文，不要写成开放问答或长段分析。只需要围绕错因做轻引导，让孩子自己补出原因
- improvement_summary_prompt: string，用于第二个书写区。请写成多行字符串：第一行是这个书写区的小标题；后续内容也必须是简短挖空题正文，不要写成大段自由总结。只需要轻轻引导孩子写“接下来准备怎么补、以后做题先提醒自己什么”
- structured_content: object，供后续四区 PDF、老师复核和长期闭环共用的结构化内容边界。字段至少包含：
  - mistake_focus: string，本题真正要纠正的错因焦点，短句即可
  - review_goal: string，这次复盘要达到的具体目标，短句即可
  - method_hint_lines: array[string]，2 到 3 条方法提醒短句，不能直接泄露完整答案；优先写成“先……再……最后……”这种带做动作链
  - blank_review_blocks: array[object]，每个 object 至少包含 title 和 lines；lines 是 1 到 2 句挖空复盘句
  - teacher_feedback: string，可留空；给老师后续批注或系统预留
  - confirmation_reasons: array[string]，可留空；只放结构化原因标识，不写成长解释
- answer: string，用于 PDF 最后的“答案与关键步骤”页，必须是这道题的标准答案或结论
- key_steps: array[string]，用于 PDF 最后的“答案与关键步骤”页，必须是推出答案的 2 到 4 个关键步骤
- pitfall_reminder: string，用于 PDF 最后的“答案与关键步骤”页，提醒本题最容易再次犯的 1 个错误

严格规则：
1. 不要在 reason_blank_prompt 或 improvement_summary_prompt 里直接给出原题答案，也不要在这两个学生书写区里提示孩子该怎样把这道题一步一步做对；标准答案和关键步骤只允许放在 answer、key_steps、pitfall_reminder 字段里。
2. 生成内容主要依据孩子自述错因、顶层错因分类和补充备注；题目内容必须用于提取本题的对象、条件、问法或符号，让填空题具像到这道题，但不要把重点放在讲题上。
2.a 如果输入里提供了 reflection_summary、question_structured、knowledge_tags，就优先把它们当成这道题的主信息脊柱；child_reason_text、cause_note 和 topic_category 作为兼容补充，不要忽略更完整的结构化反思。
2.b 内容证据优先级固定为：student_transcript > student_reason_text/学生原答案 > question_text/OCR/图片线索 > standard_solution > knowledge_tags/reflection_summary > 通用题型经验。高优先级信息存在时，不要绕开它去套低优先级标签。
2.c 错因复盘必须优先基于 student_transcript。如果 student_transcript 存在，先判断学生真实卡点：他在哪一步误解、遗漏、跳步，或把哪个条件没有翻译成数学关系；必须结合本题条件解释。没有录音转录时，只能根据题目条件、学生文字、标准解法和常见题型写“本题常见卡点是”“最容易漏的是”，不得写成“学生一定是……”。
2.c.1 当 student_transcript 缺失、student_reason_text 缺失或过于模糊、OCR 识别不完整、题干只剩图片线索、或错因解析失败时，自动进入 fallback 模式。fallback 模式下，不要直接输出“认真审题”“注意关键步骤”“下次多练”这类通用反思。
2.c.2 fallback 模式下，你必须先在内部完整过一遍这道题的做题分析：这道题的目标是什么、题目给了哪些关键条件、每个条件通常能推出什么、哪些条件之间需要建立联系、第一步应该先看什么、学生最可能卡在哪里、这题真正考的是哪类思维。这个内部分析只用于生成引导式挖空，不要把整段解析原样输出给学生。
2.c.3 fallback 模式产出的挖空复盘，重点要引导学生回答“看到这个条件，我应该想到什么”“这个条件能推出什么关系”“当前目标和已知条件之间缺了哪座桥”“我应该先找角度关系、长度关系、函数关系、受力关系还是代数关系”，不要只带学生重复计算。
2.d 下次提醒不是复述本题答案，而是总结可迁移的题型动作。几何题要优先把平行、垂直、等角、60°、辅助点分别翻译成可用关系；方程、函数、行程等题也要写成下次先做什么、先检查什么、如何触发正确方法。
2.e 挖空复盘必须从错因复盘和下次提醒里抽取关键数学动作、关键条件或题型框架。禁止出现“我这题错在 ______”“下次我要先看 ______”“我要注意 ______”“这一步需要先看清 ______”这类没有上下文的空格；每个空格前后必须让学生知道要填什么。
2.f structured_content.blank_review_blocks 必须稳定包含“错因复盘”和“下次提醒”两类 block；可以用更具体标题，但 title 或 lines 里必须看得出这两类用途。
2.g 整体语气要像老师把学生重新带回题目，不像在写分析报告。优先写“先看什么、先判断什么、再把什么改写成什么、最后检查什么”，少写“你的问题是……”“本次目标是……”这类评语句。
2.h 每道题至少给学生一个清晰的“入口动作”。读完方法提醒后，学生应该知道这题重做时第一步先写什么、先圈什么、先判断什么。
2.i method_hint_lines、reason_blank_prompt、improvement_summary_prompt 都优先写成动作链，不要只写判断句。尽量出现“先……再……最后……”或“先由……推出……，再把……改写成……，最后检查……”这种可执行顺序。
2.j 不同题型不要共用同一套 fallback 话术。至少按下面的入口来组织引导：几何题先看角、平行、垂直、相似、圆、辅助线、面积关系；代数题先看目标式、已知式、变形方向、因式分解、代换关系；函数题先看定义域、图像特征、交点、单调性、极值、参数意义；微积分题先看求导/积分对象、变量关系、边界条件、几何意义；力学题先看受力、运动状态、约束条件、方向、守恒或方程选择；概率统计题先看事件定义、条件概率、分布类型、独立性、样本空间。
3. 不要单独生成“下次提醒”或类似的第三个提示框；所有辅助都必须融进上面两个书写区里。
4. 不要把两个书写区的小标题固定成“把错因补完整”“写一写以后怎么做”等统一模板，要根据每题错因自然生成。
5. 两个书写区都要以挖空题为主，不要把其中任何一个写成纯叙述、开放作文题或老师提示语。
6. reason_blank_prompt 聚焦“这题为什么错”，优先把孩子语音/文字里提到的具体遗漏、误判、步骤顺序写进填空句；不要把孩子没说过或题目里没明确给出的细节硬写成确定事实。
7. improvement_summary_prompt 聚焦“接下来怎么补、以后先提醒自己什么”，仍然要写成挖空题，不要变成解题教学，也不要替孩子把计划写得过满过细。
8. 每个书写区正文控制在 1 到 2 句，2 到 3 个 ______ 空格即可；不要为了凑空格写成长段反思。
9. 不要在挖空题后面再追加纯写字线、自由总结、长段说明或“请写一写”的作文式提示。
10. 如果是细节问题，优先围绕检查顺序、符号、单位、抄写和验算来轻量组织提示。
11. 如果是审题问题，优先围绕看清条件、关键词和已知信息来轻量组织提示。
12. 如果是方法问题，优先围绕先判断方法是否合适、有没有用对思路来轻量组织提示。
13. 如果是知识点问题，优先围绕先回忆规则、定义或判断依据，再写一句接下来怎么补。
14. 如果输入里有 topic_category，就必须把 topic_category 当成知识点靶心；不要只写“这个知识点”“相关知识点”。例如 topic_category 是“行程”，就写“相遇问题里的速度和时间关系”；topic_category 是“第三问漏分类讨论”，就写“点 P 在原点左边和右边两种情况”。
15. 如果 primary_error_type、cause_note 或 child_reason_text 更像具体错因，就必须把具体错因写进题目化填空。不要只写“错因”“计算错因”“方法问题”；要写成“速度和时间对应关系写反”“第三问只考虑一种位置”“去分母时常数项漏乘”这类可操作表达。
16. reason_blank_prompt 的标题必须从题目和错因中取具体对象，例如“【相遇关系辨析】”“【分类讨论补全】”“【去分母检查】”，不要使用“【知识解析】”“【错因定位】”这类空标题。
17. improvement_summary_prompt 至少有一句要写出下次先检查的具体动作，例如“先标出相向而行的速度和总路程”“先列出 P 在原点两侧的情况”“先给等式两边每一项同乘分母”。
18. 句子要自然，适合小学/初中学生抄写和填写，不要出现工程术语。
19. 像复习计划里的填空题一样，把空放在“本题具体要核对的词、条件、关系、范围、单位、顺序”上；避免只写“这题可能因为对 ______ 的性质理解不透彻”这种泛化句。
20. 示例：若题目出现“定义域 [m-4,3m]、x∈[0,3m]、f(x) 单调递减、比较 f(x+1) 与 f(2x-m)”，不要写“复习函数定义和性质”；可以写“本题先核对两个自变量 x+1、2x-m 是否都落在 ______，再利用 f(x) 单调递减把 f(x+1)>f(2x-m) 转成 ______ 的不等式。”
21. reason_blank_prompt 和 improvement_summary_prompt 要像老师手写给学生的一两句短提醒，自然、有逻辑、少废话；不要出现“这题不是简单写”“AI”“模型”“生成”“分析如下”等 AI 套话。
22. 不要出现“本题重点修正”；不要出现“订正时先补全”；不要写“这一步”“重新写完整过程并检查答案范围”这类统一模板句；要直接写这题真正要补的动作。
23. 不要使用项目符号、圆点、编号列表或类似 bullet 的符号；每个书写区正文直接写 1 到 2 句短句。
24. answer 要简洁准确；key_steps 要能独立解释答案从哪里来，不要只写“计算可得”“由题意得”这类空泛步骤。
25. title 控制在 8 到 24 个字。"""

WRONG_QUESTION_PRACTICE_PACK_VARIANT_PROMPT = """你是错题练习变式题设计助手。
你会收到某个学生的真实错题、目标复习方向和需要补足的题数。请生成同错因变式题。

只返回 JSON，不要输出解释。
返回字段：
- items: array

items 每一项包含：
- variant_id: string，例如 variant-1
- source_record_id: string，参考的真实错题 ID
- question_text: string，新的练习题题面
- training_goal: string，本题训练目标
- answer: string，标准答案
- key_steps: array[string]，关键步骤
- pitfall_reminder: string，易错提醒
- difficulty: string，基础 / 中等 / 提升

严格规则：
1. 必须生成同错因变式题，不跨错因、不换训练目标。
2. 如果目标是去分母漏乘，题目必须考察等式两边每一项同乘。
3. 如果目标是符号、审题、步骤遗漏或粗心，题目必须专门触发该错误原因。
4. 题目必须可解，答案必须唯一且与关键步骤一致。
5. 不要在 question_text 里泄露答案、关键步骤或易错提醒。
6. 难度要贴近原题，不要明显超出学生当前学段。
7. 生成题数量必须等于 requested_count。"""

WRONG_QUESTION_PRACTICE_PACK_VARIANT_REVIEW_PROMPT = """你是错题练习变式题审稿老师。
请检查变式题是否可直接给学生练习。

检查项：
1. 题目可解。
2. 标准答案与题目一致，答案一致。
3. 关键步骤能推出答案。
4. 题目确实考察目标错因。
5. 没有跨到其它错因。
6. 学生题面没有泄露答案。

第一行必须只写：
结论：通过
或
结论：不通过

后续再用一句话说明原因。"""

WRONG_QUESTION_PRACTICE_SCHEMA_VERSION = "wrong_question_practice_schema.v1"
WRONG_QUESTION_PRACTICE_PROMPT_VERSION = "wrong_question_practice_prompt.2026-06-05"
WRONG_QUESTION_PRACTICE_TEMPLATE_VERSION = "wrong_question_practice_template.2026-06-05"
WRONG_QUESTION_PRACTICE_RULE_VERSION = "wrong_question_practice_rules.2026-06-05"

WEEKLY_WRONG_QUESTION_FOLLOWUP_PROMPT = """你是老师微信沟通助手。
你会收到学生本周错题概况，请写一段老师可以直接发给家长的微信。

要求：
1. 像老师真实发给家长的微信，语气自然、具体、温和。
2. 不要写成报告、通知、AI 总结或系统分析。
3. 避免报告感表达，比如“本周错题主要集中在”“建议家长配合”“知识薄弱点”“提升能力”。
4. 控制在 2 到 3 段微信可直接发送的短段落。
5. 不提小程序、系统、AI、后台、数据分析。
6. 如果有练习单，可以自然说“我这边也配了一份小练习/巩固练习”，不要说小程序里生成了什么。
7. 可以称呼“某某妈妈/爸爸”，但不要过度客套。"""

_WRONG_QUESTION_TEXT_FAILURE_MARKERS = {
    "",
    "无法识别",
    "看不清",
    "题目缺失",
    "无法看清",
    "识别失败",
}

_BROKEN_NEWLINE_LATEX_COMMAND_PATTERN = re.compile(
    r"(?<![。！？.!?：:；;])\n(?=(?:eq\b|otin\b|abla\b|mid\b|parallel\b|subset(?:eq)?\b|supset(?:eq)?\b|rightarrow\b|leftarrow\b|Rightarrow\b|Leftarrow\b|iff\b))"
)


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


def _normalize_wrong_question_recognition_result(payload: dict) -> dict:
    is_geometry = bool(payload.get("is_geometry"))
    question_text = str(payload.get("question_text") or "").strip()
    confidence = str(payload.get("confidence") or "").strip()
    notes = str(payload.get("notes") or "").strip()
    diagram_type = str(payload.get("diagram_type") or "").strip()
    raw_diagram_spec = payload.get("diagram_spec")
    diagram_spec = raw_diagram_spec if isinstance(raw_diagram_spec, dict) else None
    if diagram_spec and not diagram_type:
        diagram_type = str(diagram_spec.get("type") or "").strip()
    if not diagram_spec:
        diagram_type = diagram_type if diagram_type and diagram_type != "none" else ""
    try:
        image_rotation_degrees = int(payload.get("image_rotation_degrees") or 0)
    except (TypeError, ValueError):
        image_rotation_degrees = 0
    if image_rotation_degrees not in {0, 90, 180, 270}:
        image_rotation_degrees = 0

    normalized_text = _repair_wrong_question_latex_transport(question_text)
    normalized_text = normalized_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_text = "\n".join(line.strip() for line in normalized_text.split("\n")).strip()
    normalized_text = re.sub(r"\n{3,}", "\n\n", normalized_text)

    if is_geometry:
        return {
            "is_geometry": True,
            "question_text": normalized_text,
            "confidence": confidence,
            "notes": notes,
            "image_rotation_degrees": image_rotation_degrees,
            "diagram_type": diagram_type,
            "diagram_spec": diagram_spec,
        }

    compact_text = re.sub(r"\s+", "", normalized_text)
    if normalized_text in _WRONG_QUESTION_TEXT_FAILURE_MARKERS or len(compact_text) < 6:
        raise ValueError("题目识别失败，请重新识别")

    return {
        "is_geometry": False,
        "question_text": normalized_text,
        "confidence": confidence,
        "notes": notes,
        "image_rotation_degrees": image_rotation_degrees,
        "diagram_type": diagram_type,
        "diagram_spec": diagram_spec,
    }


def _request_wrong_question_recognition_attempt(
    image_url: str,
    *,
    revision_feedback: str = "",
    client=None,
) -> dict:
    active_client = client or _get_vision_client()
    user_instruction = "请判断这道错题是否属于几何题，提取题目文本，并在需要图像时输出可重绘的 diagram_spec。"
    if revision_feedback:
        user_instruction = (
            "上一版识别没有通过质量检查。请根据下面的审稿意见重新识别并重写题目文本：\n"
            f"{revision_feedback}\n\n"
            "只保留原始题目主体，忽略学生手写答案、草稿、订正、批改痕迹和解题过程。"
            "先判断图片正确阅读方向，并返回原图需要顺时针旋转的 image_rotation_degrees。"
            "如果原题包含几何图、数轴、表格、函数图像或示意图，必须用文字补足图中关键信息，不要只写“如图所示”，并尽量输出可重绘的 diagram_spec。"
        )

    response = active_client.chat.completions.create(
        model=_get_vision_model(),
        messages=[
            {"role": "system", "content": WRONG_QUESTION_RECOGNITION_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_instruction},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return _loads_model_json(response.choices[0].message.content)


def _collect_wrong_question_latex_render_issues(question_text: str) -> list[str]:
    normalized_text = str(question_text or "").strip()
    if not normalized_text:
        return []

    checker_script = Path(__file__).resolve().parent / "frontend" / "scripts" / "checkWrongQuestionLatex.mjs"
    if not checker_script.exists():
        return []

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as temp_file:
        json.dump({"questionText": normalized_text}, temp_file, ensure_ascii=False)
        temp_file_path = temp_file.name

    try:
        result = subprocess.run(
            ["node", str(checker_script), temp_file_path],
            cwd=str(Path(__file__).resolve().parent),
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    finally:
        try:
            Path(temp_file_path).unlink(missing_ok=True)
        except OSError:
            pass

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        if result.returncode != 0:
            stderr = str(result.stderr or "").strip()
            return [stderr or f"LaTeX 渲染检查执行失败（exit code {result.returncode}）"]
        return ["LaTeX 渲染检查返回了无法解析的结果"]

    if result.returncode != 0 and not isinstance(payload, dict):
        stderr = str(result.stderr or "").strip()
        return [stderr or f"LaTeX 渲染检查执行失败（exit code {result.returncode}）"]

    issues = []
    for error in payload.get("errors") or []:
        if not isinstance(error, dict):
            continue
        source = str(error.get("source") or "").strip()
        message = str(error.get("message") or "公式渲染失败").strip()
        issues.append(f"{message}：{source}" if source else message)
    return issues


def _review_wrong_question_recognition_quality(
    *,
    image_url: str,
    question_text: str,
    latex_issues: list[str],
    client=None,
) -> str:
    active_client = client or _get_vision_client()
    issue_text = "\n".join(f"- {issue}" for issue in latex_issues) if latex_issues else "无"
    response = active_client.chat.completions.create(
        model=_get_vision_model(),
        messages=[
            {"role": "system", "content": WRONG_QUESTION_RECOGNITION_REVIEW_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请审稿下面这版错题识别结果。\n\n"
                            f"当前题目文本：\n{question_text}\n\n"
                            f"LaTeX 渲染错误：\n{issue_text}"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
        temperature=0,
    )
    return str(response.choices[0].message.content or "").strip()


def _wrong_question_quality_review_passed(review_text: str) -> bool:
    for line in str(review_text or "").splitlines():
        normalized = re.sub(r"\s+", "", line)
        if not normalized:
            continue
        return normalized.startswith("结论：通过") or normalized.startswith("结论:通过")
    return False


def recognize_wrong_question_image(image_url: str) -> dict:
    normalized_image_url = str(image_url or "").strip()
    if not normalized_image_url:
        raise ValueError("image_url is required")

    client = None
    revision_feedback = ""
    last_failure = ""
    for _attempt in range(_WRONG_QUESTION_RECOGNITION_MAX_ATTEMPTS):
        try:
            payload = _request_wrong_question_recognition_attempt(
                normalized_image_url,
                revision_feedback=revision_feedback,
                client=client,
            )
            normalized = _normalize_wrong_question_recognition_result(payload)
        except ValueError as exc:
            last_failure = str(exc)
            revision_feedback = f"上一版识别失败：{last_failure}"
            continue

        if normalized["is_geometry"]:
            return normalized

        latex_issues = _collect_wrong_question_latex_render_issues(normalized["question_text"])
        review_text = _review_wrong_question_recognition_quality(
            image_url=normalized_image_url,
            question_text=normalized["question_text"],
            latex_issues=latex_issues,
            client=client,
        )
        if not latex_issues and _wrong_question_quality_review_passed(review_text):
            return normalized

        feedback_parts = []
        if latex_issues:
            feedback_parts.append("LaTeX 渲染检查未通过：\n" + "\n".join(f"- {issue}" for issue in latex_issues))
        if review_text:
            feedback_parts.append("AI 审稿意见：\n" + review_text)
        revision_feedback = "\n\n".join(feedback_parts).strip()
        last_failure = revision_feedback or "AI 审稿未通过"

    raise ValueError(f"题目识别质量检查未通过：{last_failure}")


def transcribe_child_reason_audio(audio_url: str) -> dict:
    normalized_audio_url = str(audio_url or "").strip()
    if not normalized_audio_url:
        raise ValueError("audio_url is required")

    audio_path = urllib.parse.urlparse(normalized_audio_url).path
    audio_suffix = Path(audio_path).suffix or ".m4a"

    with urllib.request.urlopen(normalized_audio_url, timeout=20) as response:
        audio_bytes = response.read()

    with tempfile.NamedTemporaryFile(suffix=audio_suffix) as temp_file:
        temp_file.write(audio_bytes)
        temp_file.flush()
        transcript_text = _transcribe_audio_path_locally(temp_file.name)

    return {"transcript_text": transcript_text}


def classify_wrong_question_reason(child_reason_text: str, *, question_text: str = "") -> dict:
    normalized_reason_text = str(child_reason_text or "").strip()
    if not normalized_reason_text:
        raise ValueError("child_raw_reason_text is required")

    client = _get_client()
    response = client.chat.completions.create(
        model=_get_structured_generation_model(),
        messages=[
            {"role": "system", "content": WRONG_QUESTION_REASON_CLASSIFICATION_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question_text": str(question_text or "").strip(),
                        "child_reason_text": normalized_reason_text,
                        "allowed_error_types": WRONG_QUESTION_ERROR_TYPE_OPTIONS,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    payload = _loads_model_json(response.choices[0].message.content)
    display_text = str(payload.get("display_text") or "").strip()
    primary_error_type = str(payload.get("primary_error_type") or "").strip()
    secondary_error_summary = str(payload.get("secondary_error_summary") or "").strip()
    core_issue = str(payload.get("core_issue") or "").strip()
    key_omission = str(payload.get("key_omission") or "").strip()
    next_step = str(payload.get("next_step") or "").strip()

    if primary_error_type not in WRONG_QUESTION_ERROR_TYPE_OPTIONS:
        raise ValueError("wrong question reason classification failed")
    if not secondary_error_summary:
        raise ValueError("wrong question reason classification failed")
    if not core_issue:
        core_issue = display_text or secondary_error_summary
    if not key_omission:
        key_omission = secondary_error_summary
    if not next_step:
        next_step = "下次先圈出题目条件和要求，再按步骤检查关键知识点是否用对。"

    return {
        "display_text": display_text or f"{primary_error_type}｜{secondary_error_summary}",
        "primary_error_type": primary_error_type,
        "secondary_error_summary": secondary_error_summary,
        "core_issue": core_issue,
        "key_omission": key_omission,
        "next_step": next_step,
    }


_WRONG_QUESTION_PRACTICE_PROMPT_BULLET_PREFIX_RE = re.compile(
    r"^\s*(?:[-*•·●◆◇▪▫■□▶▷①②③④⑤⑥⑦⑧⑨⑩]|\d+[.、]|[（(]?\d+[）)])\s*"
)


def _clean_wrong_question_practice_prompt_text(value: str) -> str:
    cleaned_lines = []
    for raw_line in str(value or "").split("\n"):
        line = _WRONG_QUESTION_PRACTICE_PROMPT_BULLET_PREFIX_RE.sub("", raw_line).strip()
        line = line.replace("本题重点修正：", "")
        line = line.replace("本题重点修正:", "")
        line = line.replace("订正时先补全", "先补上")
        line = line.replace("这一步", "")
        line = line.replace("再重新写完整过程并检查答案范围", "再检查答案范围")
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _normalize_string_list(values: object, *, limit: int = 0) -> list[str]:
    normalized = [
        str(item or "").strip()
        for item in (values if isinstance(values, list) else [])
        if str(item or "").strip()
    ]
    if limit > 0:
        return normalized[:limit]
    return normalized


def _normalize_optional_json_object(value: object) -> dict:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_optional_json_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return _normalize_string_list(value)
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return _normalize_string_list(parsed)


def _extract_prompt_title_and_lines(prompt: str) -> tuple[str, list[str]]:
    lines = [line.strip() for line in str(prompt or "").split("\n") if line.strip()]
    if not lines:
        return "", []
    if len(lines) == 1:
        return "", [lines[0]]
    return lines[0], lines[1:]


def _is_low_information_wrong_question_cloze(text: object) -> bool:
    raw_text = str(text or "").strip()
    normalized = re.sub(r"\s+", "", raw_text)
    if not normalized:
        return False
    low_information_patterns = [
        "我这题错在______",
        "我错在______",
        "下次我要先看______",
        "下次我会先______",
        "我要注意______",
        "这一步需要先看清______",
        "做完后我要检查______",
    ]
    if any(pattern in normalized for pattern in low_information_patterns):
        return True
    generic_guidance_patterns = [
        "认真审题",
        "理解题意",
        "先理解题意",
        "关键步骤",
        "题目条件",
        "注意条件",
        "注意计算细节",
        "检查关键条件",
        "多练类似题目",
    ]
    if any(pattern in raw_text for pattern in generic_guidance_patterns) and not _contains_specific_math_anchor(raw_text):
        return True
    return "______" in normalized and len(normalized.replace("______", "")) <= 8


def _has_low_information_wrong_question_cloze(lines: object) -> bool:
    return any(_is_low_information_wrong_question_cloze(line) for line in _normalize_string_list(lines))


def _first_non_empty_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _shorten_wrong_question_text(value: object, limit: int = 28) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return f"{text[: max(limit - 1, 1)].rstrip()}…"


def _dedupe_non_empty_texts(values: list[str], *, limit: int = 4) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        deduped.append(text)
        seen.add(text)
        if len(deduped) >= limit:
            break
    return deduped


def _contains_specific_math_anchor(text: object) -> bool:
    raw_text = str(text or "").strip()
    if not raw_text:
        return False
    if re.search(r"[A-Z]{1,3}|\d|[=<>≤≥⊥∥∠△□○%+\-×÷/\\^]", raw_text):
        return True
    specific_keywords = [
        "垂直",
        "平行",
        "等角",
        "相似",
        "辅助线",
        "面积",
        "角平分线",
        "切线",
        "分母",
        "因式",
        "代换",
        "移项",
        "方程",
        "定义域",
        "单调",
        "交点",
        "极值",
        "导数",
        "积分",
        "受力",
        "守恒",
        "样本空间",
        "条件概率",
        "分布",
        "速度",
        "位移",
    ]
    return any(keyword in raw_text for keyword in specific_keywords)


def _is_weak_wrong_question_anchor(text: object) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True
    if re.fullmatch(r"[xyzamn]", normalized):
        return True
    return normalized in {"条件", "关系", "目标", "题目条件"}


def _combine_wrong_question_analysis_text(context: dict) -> str:
    question_structured = context.get("question_structured") if isinstance(context.get("question_structured"), dict) else {}
    knowledge_tags = context.get("knowledge_tags") if isinstance(context.get("knowledge_tags"), list) else []
    parts = [
        str(context.get("question_text") or "").strip(),
        str(question_structured.get("stem") or "").strip(),
        str(context.get("topic_category") or "").strip(),
        " ".join(str(tag or "").strip() for tag in knowledge_tags if str(tag or "").strip()),
        str(context.get("standard_solution") or "").strip(),
    ]
    return "\n".join(part for part in parts if part)


def _infer_wrong_question_practice_kind(context: dict) -> str:
    analysis_text = _combine_wrong_question_analysis_text(context)
    if context.get("is_geometry"):
        return "geometry"

    rules = [
        ("calculus", ["导数", "积分", "极限", "微分", "切线斜率", "变化率", "导函数"]),
        ("mechanics", ["受力", "牛顿", "加速度", "位移", "速度变化", "约束条件", "守恒", "动量", "能量", "功率"]),
        ("probability", ["概率", "统计", "随机", "样本空间", "条件概率", "独立", "分布", "期望", "方差", "频率"]),
        ("function", ["函数", "定义域", "值域", "图像", "单调", "极值", "零点", "交点", "参数", "斜率"]),
        ("algebra", ["方程", "代数", "因式", "分母", "配方", "代换", "移项", "根式", "整式", "分式", "化简", "求值"]),
        ("geometry", ["垂直", "平行", "等角", "相似", "圆", "辅助线", "面积", "角平分线", "切线", "三角形"]),
    ]
    for kind, keywords in rules:
        if any(keyword in analysis_text for keyword in keywords):
            return kind
    if re.search(r"[A-Z]{1,3}\s*[⊥∥]|∠[A-Z]{1,3}|△[A-Z]{3}", analysis_text):
        return "geometry"
    return "generic"


def _extract_wrong_question_goal(context: dict, kind: str) -> str:
    question_structured = context.get("question_structured") if isinstance(context.get("question_structured"), dict) else {}
    question_text = _first_non_empty_text(context.get("question_text"), question_structured.get("stem"))
    for pattern in [
        r"(求证[^。；，,\n]+)",
        r"(证明[^。；，,\n]+)",
        r"(求[^。；，,\n]+)",
        r"(解[^。；，,\n]+)",
        r"(化简[^。；，,\n]+)",
        r"(比较[^。；，,\n]+)",
        r"(判断[^。；，,\n]+)",
    ]:
        match = re.search(pattern, question_text)
        if match:
            return _shorten_wrong_question_text(match.group(1), limit=22)

    defaults = {
        "geometry": "找到图上能连到目标的关系",
        "algebra": "把已知式稳稳变到目标式",
        "function": "判断函数关系或参数范围",
        "calculus": "判断变化关系或边界条件",
        "mechanics": "连起受力、状态和方程",
        "probability": "先定事件关系再下手计算",
        "generic": "先把已知和目标连起来",
    }
    return defaults.get(kind, defaults["generic"])


def _extract_wrong_question_condition_anchors(context: dict, kind: str) -> list[str]:
    analysis_text = _combine_wrong_question_analysis_text(context)
    knowledge_tags = context.get("knowledge_tags") if isinstance(context.get("knowledge_tags"), list) else []
    matches: list[str] = []

    for pattern in [
        r"[A-Z]{1,3}\s*⊥\s*[A-Z]{1,3}",
        r"[A-Z]{1,3}\s*∥\s*[A-Z]{1,3}",
        r"∠[A-Z]{1,3}\s*=\s*∠[A-Z]{1,3}",
        r"\b\d+°",
        r"\b[xyzamn]\b",
        r"f\([^)]*\)",
    ]:
        matches.extend(match.group(0).replace(" ", "") for match in re.finditer(pattern, analysis_text))

    keyword_map = {
        "geometry": ["垂直", "平行", "等角", "相似", "圆", "辅助线", "面积", "角平分线", "切线", "中点"],
        "algebra": ["分母", "因式", "代换", "移项", "配方", "未知数", "比例", "同类项", "根式", "方程"],
        "function": ["定义域", "图像", "交点", "单调", "极值", "参数", "零点", "自变量", "函数值"],
        "calculus": ["导数", "积分", "边界条件", "变化率", "切线", "极值", "单调", "几何意义"],
        "mechanics": ["受力", "速度", "加速度", "位移", "方向", "守恒", "约束条件", "平衡", "运动状态"],
        "probability": ["事件", "条件概率", "样本空间", "独立", "分布", "频率", "均值", "方差"],
        "generic": ["条件", "关系", "目标"],
    }
    for keyword in keyword_map.get(kind, keyword_map["generic"]):
        if keyword in analysis_text:
            matches.append(keyword)

    matches.extend(str(tag or "").strip() for tag in knowledge_tags if str(tag or "").strip())
    topic_anchor = str(context.get("topic_category") or "").strip()
    if topic_anchor:
        matches.append(topic_anchor)

    return _dedupe_non_empty_texts(matches, limit=4)


def _build_wrong_question_guided_analysis(context: dict) -> dict:
    kind = _infer_wrong_question_practice_kind(context)
    goal = _extract_wrong_question_goal(context, kind)
    conditions = _extract_wrong_question_condition_anchors(context, kind)
    topic_anchor = _first_non_empty_text(context.get("topic_category"), "同类题")
    focus_source = _first_non_empty_text(
        context.get("student_transcript"),
        context.get("student_reason_text"),
        context.get("cause_note"),
        (
            context.get("reflection_summary", {}).get("unknown_step")
            if isinstance(context.get("reflection_summary"), dict)
            else ""
        ),
    )
    focus_hint = _shorten_wrong_question_text(focus_source, limit=24)
    primary_condition = conditions[0] if conditions else ""
    secondary_condition = conditions[1] if len(conditions) > 1 else ""
    condition_pair = (
        f"{primary_condition} 和 {secondary_condition}"
        if primary_condition and secondary_condition and primary_condition != secondary_condition
        else primary_condition
    )

    profiles = {
        "geometry": {
            "reason_title": "【图上先找关系】",
            "reminder_title": "【下次先连条件】",
            "default_pair": "图上的已知角和辅助线",
            "focus_condition": primary_condition or "垂直、平行或等角",
            "relation_bucket": "角度、长度、相似或辅助线关系",
            "start_action": "先在图上标出已知角、直角或对应边",
            "bridge_bucket": "角度、长度、相似还是辅助线",
        },
        "algebra": {
            "reason_title": "【式子先看方向】",
            "reminder_title": "【下次先找变形】",
            "default_pair": "已知式和目标式",
            "focus_condition": primary_condition or "分母、因式或代换条件",
            "relation_bucket": "等式、变形或代换关系",
            "start_action": "先盯住目标式和已知式差在哪一步",
            "bridge_bucket": "移项、去分母、因式还是代换",
        },
        "function": {
            "reason_title": "【先盯定义域和图像】",
            "reminder_title": "【下次先看函数桥】",
            "default_pair": "定义域和图像特征",
            "focus_condition": primary_condition or "定义域、单调或参数条件",
            "relation_bucket": "单调、交点或参数关系",
            "start_action": "先圈出自变量范围和图像线索",
            "bridge_bucket": "定义域、图像、单调还是参数",
        },
        "calculus": {
            "reason_title": "【先看对象和边界】",
            "reminder_title": "【下次先定变化关系】",
            "default_pair": "求导对象和边界条件",
            "focus_condition": primary_condition or "导数、积分或边界条件",
            "relation_bucket": "变化率、单调或几何意义",
            "start_action": "先看要求导还是积分，再圈边界条件",
            "bridge_bucket": "变化率、单调、边界还是几何意义",
        },
        "mechanics": {
            "reason_title": "【先画受力和状态】",
            "reminder_title": "【下次先选方程】",
            "default_pair": "受力情况和运动状态",
            "focus_condition": primary_condition or "受力、方向或约束条件",
            "relation_bucket": "受力、守恒或运动方程",
            "start_action": "先分清受力、方向和当前运动状态",
            "bridge_bucket": "受力、守恒、位移还是速度关系",
        },
        "probability": {
            "reason_title": "【先定事件和样本】",
            "reminder_title": "【下次先拆事件】",
            "default_pair": "事件定义和样本空间",
            "focus_condition": primary_condition or "事件、条件概率或分布信息",
            "relation_bucket": "事件、独立性或分布关系",
            "start_action": "先把事件和样本空间写清楚",
            "bridge_bucket": "事件、独立、条件概率还是分布",
        },
        "generic": {
            "reason_title": "【先把条件连起来】",
            "reminder_title": "【下次先找入口】",
            "default_pair": "题目条件和目标",
            "focus_condition": primary_condition or "关键条件",
            "relation_bucket": "条件和目标之间的数学关系",
            "start_action": "先圈出已知和问题在问什么",
            "bridge_bucket": "条件、关系、式子还是图形线索",
        },
    }
    profile = profiles.get(kind, profiles["generic"])
    topic_phrase = topic_anchor if topic_anchor.endswith("题") else f"{topic_anchor}题"
    if not condition_pair:
        condition_pair = profile["default_pair"]
    focus_condition = profile["focus_condition"] if _is_weak_wrong_question_anchor(primary_condition) else primary_condition

    return {
        "kind": kind,
        "goal": goal,
        "topic_anchor": topic_anchor,
        "topic_phrase": topic_phrase,
        "focus_hint": focus_hint,
        "condition_pair": condition_pair,
        "focus_condition": focus_condition,
        "relation_bucket": profile["relation_bucket"],
        "start_action": profile["start_action"],
        "bridge_bucket": profile["bridge_bucket"],
        "reason_title": profile["reason_title"],
        "reminder_title": profile["reminder_title"],
    }


def _pick_condition_anchor(context: dict) -> str:
    question_text = str(context.get("question_text") or "").strip()
    for pattern in (r"[A-Z]{1,3}\s*⊥\s*[A-Z]{1,3}", r"∠[A-Z]{3}\s*=\s*∠[A-Z]{3}", r"\b\d+°"):
        match = re.search(pattern, question_text)
        if match:
            return match.group(0).replace(" ", "")
    structured = context.get("question_structured") if isinstance(context.get("question_structured"), dict) else {}
    return _first_non_empty_text(structured.get("stem"), question_text, context.get("topic_category"), "题目条件")


def _build_contextual_wrong_question_practice_blocks(context: dict) -> list[dict]:
    reflection = context.get("reflection_summary") if isinstance(context.get("reflection_summary"), dict) else {}
    knowledge_tags = context.get("knowledge_tags") if isinstance(context.get("knowledge_tags"), list) else []
    student_transcript = str(context.get("student_transcript") or "").strip()
    reason_text = str(context.get("student_reason_text") or context.get("child_reason_text") or "").strip()
    why_wrong = _first_non_empty_text(reflection.get("why_wrong"), context.get("cause_note"))
    unknown_step = _first_non_empty_text(reflection.get("unknown_step"), context.get("topic_category"))
    help_preference = _first_non_empty_text(reflection.get("help_preference"))
    tag_anchor = "、".join(str(tag or "").strip() for tag in knowledge_tags[:3] if str(tag or "").strip())
    analysis = _build_wrong_question_guided_analysis(context)
    condition_anchor = _pick_condition_anchor(context)
    source_anchor = _first_non_empty_text(student_transcript, reason_text, why_wrong, unknown_step)
    source_prefix = f"先回到“{_shorten_wrong_question_text(source_anchor, limit=22)}”这一步，" if source_anchor else ""
    condition_pair = analysis["condition_pair"] or condition_anchor
    focus_condition = analysis["focus_condition"] or condition_anchor

    reason_line = (
        f"{source_prefix}当目标是“{analysis['goal']}”时，先看 {condition_pair}，"
        "想它们之间可能连出 ______。"
    )
    reason_second_line = (
        f"这题先别急着算，关键是把 {focus_condition} "
        f"翻成可用的 ______，再决定下一步。"
    )

    if help_preference:
        reminder_line = (
            f"下次遇到 {analysis['topic_phrase']}，先按“{_shorten_wrong_question_text(help_preference, limit=18)}”的顺序，"
            f"{analysis['start_action']}，再找 ______。"
        )
    else:
        reminder_line = (
            f"下次遇到 {analysis['topic_phrase']}，我先{analysis['start_action']}，"
            "先找 ______，再下笔。"
        )

    bridge_source = tag_anchor or analysis["bridge_bucket"]
    reminder_second_line = (
        f"如果一时接不上，就回头问自己：现在缺的是 {bridge_source} 里的哪一座 ______。"
    )

    return [
        {"title": analysis["reason_title"], "lines": [reason_line, reason_second_line]},
        {"title": analysis["reminder_title"], "lines": [reminder_line, reminder_second_line]},
    ]


def _normalize_wrong_question_practice_structured_content(
    source: dict,
    *,
    reason_blank_prompt: str,
    improvement_summary_prompt: str,
    pitfall_reminder: str,
    source_context: dict | None = None,
) -> dict:
    structured_source = source.get("structured_content")
    if not isinstance(structured_source, dict):
        structured_source = {}

    reason_title, reason_lines = _extract_prompt_title_and_lines(reason_blank_prompt)
    improvement_title, improvement_lines = _extract_prompt_title_and_lines(improvement_summary_prompt)

    mistake_focus = str(
        structured_source.get("mistake_focus")
        or structured_source.get("mistakeFocus")
        or reason_title
        or ""
    ).strip()
    review_goal = str(
        structured_source.get("review_goal")
        or structured_source.get("reviewGoal")
        or improvement_title
        or ""
    ).strip()
    method_hint_lines = _normalize_string_list(
        structured_source.get("method_hint_lines") or structured_source.get("methodHintLines"),
        limit=3,
    )
    if not method_hint_lines and pitfall_reminder:
        method_hint_lines = [str(pitfall_reminder).strip()]

    raw_blocks = structured_source.get("blank_review_blocks") or structured_source.get("blankReviewBlocks")
    normalized_blocks = []
    if isinstance(raw_blocks, list):
        for raw_block in raw_blocks:
            block = raw_block if isinstance(raw_block, dict) else {}
            block_title = str(block.get("title") or "").strip()
            block_lines = _normalize_string_list(block.get("lines"), limit=2)
            if block_title or block_lines:
                normalized_blocks.append(
                    {
                        "title": block_title,
                        "lines": block_lines,
                    }
                )
    if not normalized_blocks:
        fallback_blocks = []
        if reason_title or reason_lines:
            fallback_blocks.append({"title": reason_title, "lines": reason_lines[:2]})
        if improvement_title or improvement_lines:
            fallback_blocks.append({"title": improvement_title, "lines": improvement_lines[:2]})
        normalized_blocks = [block for block in fallback_blocks if block["title"] or block["lines"]]
    if any(_has_low_information_wrong_question_cloze(block.get("lines")) for block in normalized_blocks):
        contextual_blocks = _build_contextual_wrong_question_practice_blocks(source_context or {})
        if contextual_blocks:
            normalized_blocks = contextual_blocks

    teacher_feedback = str(
        structured_source.get("teacher_feedback")
        or structured_source.get("teacherFeedback")
        or ""
    ).strip()
    confirmation_reasons = _normalize_string_list(
        structured_source.get("confirmation_reasons") or structured_source.get("confirmationReasons"),
    )

    return {
        "mistake_focus": mistake_focus,
        "review_goal": review_goal,
        "method_hint_lines": method_hint_lines,
        "blank_review_blocks": normalized_blocks,
        "teacher_feedback": teacher_feedback,
        "confirmation_reasons": confirmation_reasons,
    }


def _normalize_wrong_question_practice_sheet_material(
    payload: dict,
    *,
    expected_record_ids: list[str],
    item_contexts_by_record_id: dict[str, dict] | None = None,
) -> dict:
    title = str(payload.get("title") or "").strip()
    raw_items = payload.get("items")
    if not title:
        title = "错题练习"
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("wrong question practice sheet generation failed")

    normalized_items = []
    for index, raw_item in enumerate(raw_items):
        source = raw_item if isinstance(raw_item, dict) else {}
        wrong_question_record_id = str(source.get("wrong_question_record_id") or "").strip()
        if not wrong_question_record_id and index < len(expected_record_ids):
            wrong_question_record_id = expected_record_ids[index]
        source_context = {}
        if item_contexts_by_record_id:
            source_context = item_contexts_by_record_id.get(wrong_question_record_id) or {}
        ai_hint = str(source.get("ai_hint") or "").strip()
        reason_blank_prompt = str(source.get("reason_blank_prompt") or "").strip()
        improvement_summary_prompt = str(source.get("improvement_summary_prompt") or "").strip()
        answer = str(source.get("answer") or "").strip()
        key_steps = source.get("key_steps")
        normalized_key_steps = [
            str(step or "").strip()
            for step in (key_steps if isinstance(key_steps, list) else [])
            if str(step or "").strip()
        ]
        pitfall_reminder = str(source.get("pitfall_reminder") or "").strip()

        reason_blank_prompt = reason_blank_prompt.replace("\r\n", "\n").replace("\r", "\n").strip()
        improvement_summary_prompt = improvement_summary_prompt.replace("\r\n", "\n").replace("\r", "\n").strip()
        reason_blank_prompt = _clean_wrong_question_practice_prompt_text(reason_blank_prompt)
        improvement_summary_prompt = _clean_wrong_question_practice_prompt_text(improvement_summary_prompt)

        reason_lines = [line.strip() for line in reason_blank_prompt.split("\n") if line.strip()]
        improvement_lines = [line.strip() for line in improvement_summary_prompt.split("\n") if line.strip()]

        if reason_lines:
            if len(reason_lines) >= 2:
                reason_title = reason_lines[0]
                reason_body = "\n".join(reason_lines[1:])
            else:
                reason_title = ""
                reason_body = reason_lines[0]
            if _is_low_information_wrong_question_cloze(reason_body):
                contextual_blocks = _build_contextual_wrong_question_practice_blocks(source_context)
                reason_title = contextual_blocks[0]["title"]
                reason_body = "\n".join(contextual_blocks[0]["lines"])
            while reason_body.count("______") < 2:
                reason_body = f"{reason_body.rstrip('。')} ______。"
            reason_blank_prompt = (
                f"{reason_title}\n{reason_body}".strip()
                if reason_title
                else reason_body
            )

        if improvement_lines:
            if len(improvement_lines) >= 2:
                improvement_title = improvement_lines[0]
                improvement_body = "\n".join(improvement_lines[1:])
                if _is_low_information_wrong_question_cloze(improvement_body):
                    contextual_blocks = _build_contextual_wrong_question_practice_blocks(source_context)
                    improvement_title = contextual_blocks[1]["title"]
                    improvement_body = "\n".join(contextual_blocks[1]["lines"])
                improvement_summary_prompt = f"{improvement_title}\n{improvement_body}".strip()
            else:
                improvement_body = improvement_lines[0]
                if _is_low_information_wrong_question_cloze(improvement_body):
                    contextual_blocks = _build_contextual_wrong_question_practice_blocks(source_context)
                    improvement_summary_prompt = (
                        f"{contextual_blocks[1]['title']}\n" + "\n".join(contextual_blocks[1]["lines"])
                    ).strip()
                else:
                    improvement_summary_prompt = improvement_body

        if (
            not wrong_question_record_id
            or not reason_blank_prompt
            or not improvement_summary_prompt
            or not answer
            or not normalized_key_steps
        ):
            raise ValueError("wrong question practice sheet generation failed")

        structured_content = _normalize_wrong_question_practice_structured_content(
            source,
            reason_blank_prompt=reason_blank_prompt,
            improvement_summary_prompt=improvement_summary_prompt,
            pitfall_reminder=pitfall_reminder,
            source_context=source_context,
        )

        normalized_items.append(
            {
                "wrong_question_record_id": wrong_question_record_id,
                "ai_hint": ai_hint,
                "reason_blank_prompt": reason_blank_prompt,
                "improvement_summary_prompt": improvement_summary_prompt,
                "structured_content": structured_content,
                "answer": answer,
                "key_steps": normalized_key_steps,
                "pitfall_reminder": pitfall_reminder,
            }
        )

    normalized_record_ids = [item["wrong_question_record_id"] for item in normalized_items]
    if normalized_record_ids != expected_record_ids:
        raise ValueError("wrong question practice sheet generation failed")

    base_generation_metadata = build_wrong_question_practice_generation_metadata()
    normalized_items = [
        {
            **item,
            "generation_metadata": {
                **base_generation_metadata,
                "scope": "item",
                "wrong_question_record_id": item["wrong_question_record_id"],
            },
        }
        for item in normalized_items
    ]

    return {
        "title": title,
        "generation_metadata": {
            **base_generation_metadata,
            "scope": "sheet",
            "item_count": len(normalized_items),
        },
        "items": normalized_items,
    }


def build_wrong_question_practice_generation_metadata(
    *,
    provider: str = "",
    model_version: str = "",
    entrypoint: str = "wrong_question_practice_sheet",
) -> dict:
    normalized_provider = str(provider or "").strip()
    normalized_model_version = str(model_version or "").strip()
    normalized_entrypoint = str(entrypoint or "wrong_question_practice_sheet").strip() or "wrong_question_practice_sheet"
    return {
        "schema_version": WRONG_QUESTION_PRACTICE_SCHEMA_VERSION,
        "prompt_version": WRONG_QUESTION_PRACTICE_PROMPT_VERSION,
        "template_version": WRONG_QUESTION_PRACTICE_TEMPLATE_VERSION,
        "rule_version": WRONG_QUESTION_PRACTICE_RULE_VERSION,
        "provider": normalized_provider,
        "model_version": normalized_model_version,
        "entrypoint": normalized_entrypoint,
    }


_WRONG_QUESTION_PRACTICE_PACK_TARGET_SUBSTRINGS = (
    "去分母",
    "漏乘",
    "符号",
    "审题",
    "步骤",
    "遗漏",
    "粗心",
)


def _wrong_question_practice_pack_target_tokens(target: str) -> list[str]:
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return []
    compact_target = re.sub(r"[\s,，、/／|｜;；:：\-—_()（）\[\]【】{}]+", "", normalized_target)
    raw_parts = re.split(r"[\s,，、/／|｜;；:：\-—_()（）\[\]【】{}]+", normalized_target)
    tokens = {
        part.strip()
        for part in raw_parts
        if len(part.strip()) >= 2
    }
    if len(compact_target) >= 2:
        tokens.add(compact_target)
    for substring in _WRONG_QUESTION_PRACTICE_PACK_TARGET_SUBSTRINGS:
        if substring in compact_target:
            tokens.add(substring)
    return sorted(tokens, key=len, reverse=True)


def _wrong_question_practice_pack_variant_matches_target(item: dict, target: str) -> bool:
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return True
    compact_target = re.sub(r"[\s,，、/／|｜;；:：\-—_()（）\[\]【】{}]+", "", normalized_target)
    evidence_text = "".join(
        [
            str(item.get("question_text") or ""),
            str(item.get("training_goal") or ""),
            str(item.get("pitfall_reminder") or ""),
        ]
    )
    if "去分母" in compact_target:
        has_denominator_evidence = (
            "去分母" in evidence_text
            or ("分母" in evidence_text and "同乘" in evidence_text)
            or ("等式两边" in evidence_text and "同乘" in evidence_text)
        )
        if not has_denominator_evidence:
            return False
        if "漏乘" in compact_target:
            return any(token in evidence_text for token in ("漏乘", "每一项", "常数项"))
        return True
    tokens = _wrong_question_practice_pack_target_tokens(target)
    return any(token in evidence_text for token in tokens)


def _normalize_wrong_question_practice_pack_variants(
    payload: dict,
    *,
    expected_count: int,
    target: str,
) -> list[dict]:
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list) or len(raw_items) != int(expected_count or 0):
        raise ValueError("wrong question practice pack variant generation failed")
    normalized = []
    for index, raw_item in enumerate(raw_items, start=1):
        source = raw_item if isinstance(raw_item, dict) else {}
        key_steps = source.get("key_steps")
        normalized_steps = [
            str(step or "").strip()
            for step in (key_steps if isinstance(key_steps, list) else [])
            if str(step or "").strip()
        ]
        item = {
            "variant_id": str(source.get("variant_id") or f"variant-{index}").strip(),
            "source_record_id": str(source.get("source_record_id") or "").strip(),
            "question_text": str(source.get("question_text") or "").strip(),
            "training_goal": str(source.get("training_goal") or "").strip(),
            "answer": str(source.get("answer") or "").strip(),
            "key_steps": normalized_steps,
            "pitfall_reminder": str(source.get("pitfall_reminder") or "").strip(),
            "difficulty": str(source.get("difficulty") or "基础").strip() or "基础",
        }
        if not item["question_text"] or not item["answer"] or not item["training_goal"] or not item["key_steps"]:
            raise ValueError("wrong question practice pack variant generation failed")
        if not _wrong_question_practice_pack_variant_matches_target(item, target):
            raise ValueError("wrong question practice pack variant target mismatch")
        normalized.append(item)
    return normalized


def _wrong_question_practice_pack_variant_review_passed(review_text: str) -> bool:
    for line in str(review_text or "").splitlines():
        normalized = re.sub(r"\s+", "", line)
        if not normalized:
            continue
        return normalized.startswith("结论：通过") or normalized.startswith("结论:通过")
    return False


def generate_wrong_question_practice_pack_variants(
    *,
    student_name: str,
    class_name: str,
    mode: str,
    target: str,
    requested_count: int,
    source_records: list[dict],
    include_usage: bool = False,
):
    if int(requested_count or 0) <= 0:
        return ([], {}) if include_usage else []
    normalized_records = [
        {
            "id": str(record.get("id") or "").strip(),
            "question_text": str(record.get("question_text") or "").strip(),
            "topic_category": str(record.get("topic_category") or "").strip(),
            "primary_error_type": str(record.get("primary_error_type") or "").strip(),
            "secondary_error_summary": str(record.get("secondary_error_summary") or "").strip(),
            "child_reason_text": str(record.get("child_raw_reason_text") or "").strip(),
        }
        for record in (source_records or [])
    ]
    if not normalized_records:
        raise ValueError("source_records are required")
    client = _get_client()
    response = client.chat.completions.create(
        model=_get_structured_generation_model(),
        messages=[
            {"role": "system", "content": WRONG_QUESTION_PRACTICE_PACK_VARIANT_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "student_name": str(student_name or "").strip(),
                        "class_name": str(class_name or "").strip(),
                        "mode": str(mode or "").strip(),
                        "target": str(target or "").strip(),
                        "requested_count": int(requested_count or 0),
                        "source_records": normalized_records,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    payload = _loads_model_json(response.choices[0].message.content)
    normalized = _normalize_wrong_question_practice_pack_variants(
        payload,
        expected_count=int(requested_count or 0),
        target=str(target or "").strip(),
    )
    if include_usage:
        return normalized, _usage_dict(response)
    return normalized


def review_wrong_question_practice_pack_variant(
    *,
    mode: str,
    target: str,
    variant: dict,
    client=None,
) -> str:
    active_client = client or _get_client()
    response = active_client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": WRONG_QUESTION_PRACTICE_PACK_VARIANT_REVIEW_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "mode": str(mode or "").strip(),
                        "target": str(target or "").strip(),
                        "variant": variant,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
    )
    return str(response.choices[0].message.content or "").strip()


def generate_wrong_question_practice_sheet_material(
    *,
    student_name: str,
    class_name: str,
    teacher_name: str,
    items: list[dict],
    include_usage: bool = False,
):
    if not items:
        raise ValueError("wrong question practice sheet items are required")

    expected_record_ids = [str(item.get("wrong_question_record_id") or "").strip() for item in items]
    if any(not record_id for record_id in expected_record_ids):
        raise ValueError("wrong question practice sheet items are invalid")

    normalized_items = []
    for item in items:
        reflection_summary = _normalize_optional_json_object(
            item.get("reflection_summary_snapshot_json", item.get("reflection_summary")),
        )
        question_structured = _normalize_optional_json_object(
            item.get("question_structured_snapshot_json", item.get("question_structured")),
        )
        knowledge_tags = _normalize_optional_json_string_list(
            item.get("knowledge_tags_snapshot_json", item.get("knowledge_tags")),
        )
        student_transcript = str(
            item.get("child_reason_transcript_snapshot")
            or item.get("student_transcript")
            or reflection_summary.get("summary_text")
            or ""
        ).strip()
        student_reason_text = str(
            item.get("child_reason_text_snapshot")
            or item.get("student_reason_text")
            or ""
        ).strip()
        image_url = str(item.get("image_url_snapshot") or item.get("image_url") or "").strip()
        normalized_items.append(
            {
                "wrong_question_record_id": str(item.get("wrong_question_record_id") or "").strip(),
                "question_order": int(item.get("question_order") or 0),
                "is_geometry": bool(item.get("is_geometry")),
                "question_text": str(item.get("question_text_snapshot") or "").strip(),
                "child_reason_text": student_reason_text,
                "student_reason_text": student_reason_text,
                "student_transcript": student_transcript,
                "image_url": image_url,
                "image_available": bool(image_url),
                "student_answer": str(item.get("student_answer_snapshot") or item.get("student_answer") or "").strip(),
                "standard_solution": str(item.get("standard_solution_snapshot") or item.get("standard_solution") or "").strip(),
                "primary_error_type": str(item.get("primary_error_type_snapshot") or "").strip(),
                "cause_note": str(item.get("cause_note_snapshot") or "").strip(),
                "topic_category": str(item.get("topic_category_snapshot") or item.get("topic_category") or "").strip(),
                "reflection_summary": reflection_summary,
                "question_structured": question_structured,
                "knowledge_tags": knowledge_tags,
            }
        )

    client = _get_client()
    provider = str(_load_config().get("provider") or "deepseek").strip() or "deepseek"
    model_version = _get_structured_generation_model()
    response = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": WRONG_QUESTION_PRACTICE_SHEET_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "student_name": str(student_name or "").strip(),
                        "class_name": str(class_name or "").strip(),
                        "teacher_name": str(teacher_name or "").strip(),
                        "items": normalized_items,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    payload = _loads_model_json(response.choices[0].message.content)
    item_contexts_by_record_id = {
        str(item.get("wrong_question_record_id") or "").strip(): item
        for item in normalized_items
        if str(item.get("wrong_question_record_id") or "").strip()
    }
    normalized = _normalize_wrong_question_practice_sheet_material(
        payload,
        expected_record_ids=expected_record_ids,
        item_contexts_by_record_id=item_contexts_by_record_id,
    )
    generation_metadata = build_wrong_question_practice_generation_metadata(
        provider=provider,
        model_version=model_version,
    )
    normalized["generation_metadata"] = {
        **normalized.get("generation_metadata", {}),
        **generation_metadata,
    }
    normalized["items"] = [
        {
            **item,
            "generation_metadata": {
                **item.get("generation_metadata", {}),
                **generation_metadata,
                "scope": "item",
                "wrong_question_record_id": item.get("wrong_question_record_id"),
            },
        }
        for item in normalized.get("items", [])
        if isinstance(item, dict)
    ]
    if include_usage:
        return normalized, _usage_dict(response)
    return normalized


def generate_weekly_wrong_question_followup_message(
    *,
    student_name: str,
    class_name: str,
    teacher_name: str,
    weekly_question_count: int,
    total_active_question_count: int,
    topic_categories: list[str],
    representative_reason_summaries: list[str],
    has_practice_sheet: bool,
    practice_sheet_question_count: int = 0,
    practice_sheet_topic_categories: list[str] | None = None,
    practice_sheet_reason_summaries: list[str] | None = None,
    practice_sheet_item_summaries: list[str] | None = None,
) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": WEEKLY_WRONG_QUESTION_FOLLOWUP_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "student_name": str(student_name or "").strip(),
                        "class_name": str(class_name or "").strip(),
                        "teacher_name": str(teacher_name or "").strip(),
                        "weekly_question_count": int(weekly_question_count or 0),
                        "total_active_question_count": int(total_active_question_count or 0),
                        "topic_categories": [str(item).strip() for item in topic_categories if str(item).strip()],
                        "representative_reason_summaries": [
                            str(item).strip()
                            for item in representative_reason_summaries
                            if str(item).strip()
                        ],
                        "has_practice_sheet": bool(has_practice_sheet),
                        "practice_sheet_question_count": int(practice_sheet_question_count or 0),
                        "practice_sheet_topic_categories": [
                            str(item).strip()
                            for item in (practice_sheet_topic_categories or [])
                            if str(item).strip()
                        ],
                        "practice_sheet_reason_summaries": [
                            str(item).strip()
                            for item in (practice_sheet_reason_summaries or [])
                            if str(item).strip()
                        ],
                        "practice_sheet_item_summaries": [
                            str(item).strip()
                            for item in (practice_sheet_item_summaries or [])
                            if str(item).strip()
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.5,
    )
    content = str(response.choices[0].message.content or "").strip()
    if not content:
        raise ValueError("weekly wrong question followup message generation failed")
    return content


# ─── 生成复习计划的提示词 ───────────────────────────────────────────────────────
PLAN_SYSTEM_PROMPT = r"""你是一位专业的初中学科辅导老师，擅长把课堂反馈整理成高质量课后复习计划。
你将收到课堂总结与元信息，必须返回一个可直接用于 PDF 生成的结构化 JSON。

【最高优先级：固定工作流（每次都必须严格执行）】
1) 复习节点固定为 5 天：第1天、第2天、第7天、第14天、第30天。
2) 每个复习日都必须完整覆盖整节课全部核心知识点，不能把 5 天拆成各自只复习一部分。
3) 每天复习时长控制在 10-20 分钟。
4) 题型以填空题为主，选择题为辅；选择题只承担三类功能：
   - 检查基础记忆
   - 辨析易混概念
   - 纠正常见错误
5) 必须保留“上课金句回顾”与“课堂原话回放”模块。
6) 课堂原话使用比例控制在 10%-15%，只保留高价值句子，不可过多。
7) 严禁把“作业布置”当成题目本体，不得出现“本节课布置了哪些作业/题号”等提问。
8) 每个复习日标题必须包含实际日期，按“第0天=本次生成日期”计算：
   - day1 = 第0天+1
   - day2 = 第0天+2
   - day7 = 第0天+7
   - day14 = 第0天+14
   - day30 = 第0天+30
9) 每个复习日要有差异化复习重点，但都要覆盖全课：
   - 第1天：框架回忆
   - 第2天：方法巩固
   - 第7天：题型迁移
   - 第14天：口述提问强化
   - 第30天：综合总复盘
10) 知识点加练按天固定规则：
   - 第1/2天：填空+选择混合
   - 第7/14天：老师提问口述卡片
   - 第30天：填空+选择混合

【163320式教研整理要求】
- 如果输入里出现“同一节课”的多段材料、多段录音纪要或补充材料，必须先合并成一节课理解；不要拆成多份计划，也不要遗漏后半段材料。
- 生成前必须从课堂材料中提取 6 列教研信息：方法主线、题型入口、操作步骤、易错提醒、典型例题、老师原话。
- 每个核心知识点都要写成可执行动作链：看到什么条件 → 先做什么 → 再做什么 → 易错点是什么。
- 复习计划要像 163320 版一样保留密集方法地图：既覆盖全课主题，也保留课堂原话、最终提醒、知识点加练和选择题辅助。
- 优先输出具体课堂内容，例如“看到等腰找中点”“面面夹角 60 度转线线角”“线面角正弦等于直线与法向量夹角余弦”，禁止只写泛泛学习建议。

【内容质量硬性要求】
- 所有 type="body" 与 type="fill" 的 text 必须是本节课具体内容，禁止模板占位词。
- 禁止出现“板块一/板块X/（具体题目）/（按实际填写）/（板块名）/正确答案”等元描述。
- 每道填空题都要可直接印刷给学生使用，读题后能明确考查点。
- 纯公式型填空题（只要求默写公式、字母形式或符号关系）在全部填空题中的占比不得超过 30%。
- 至少 70% 的填空题应围绕方法选择、结构识别、使用场景、推导依据、易错点或题目条件判断来设计，不能把整份复习计划做成公式默写表。
- 每个 type="fill" 的题目都必须包含 "answer"，且答案简洁明确。

【输出格式要求】
- 只返回合法 JSON，不要输出额外说明。
- 使用 ____ 表示空格（4条下划线）。
- 所有数学公式、运算式、符号必须用 $…$（行内）包裹，例如 $\frac{a}{b}$、$x^2$、$\sin\theta$、$a^2+b^2=c^2$。禁止裸写 LaTeX 命令，禁止用 **…** 等 Markdown 格式包裹公式。
- days 必须严格只包含 day=1,2,7,14,30 五项。
- 每天必须有 self_test_phrase。
- 第1/2/7天使用 type="day1" + steps；每个节点 3 个步骤，步骤3至少 6 道题。
- 第14/30天使用 type="daily" + items，但仍必须覆盖全课全部核心知识点。
【JSON 结构】
{
  "lesson_info": {
    "subject": "科目",
    "grade": "年级",
    "topic": "本节主题",
    "key_categories": ["最多6个核心知识板块"],
    "group_a": ["前半板块名称，可用于兼容展示"],
    "group_b": ["后半板块名称，可用于兼容展示"]
  },
  "full_review_topics": ["全课覆盖主题，可超过6项，用于保留方法地图"],
  "quotes": ["高价值老师原话，10%-15%比例"],
  "final_reminder_lines": ["最终提醒，必须是本节课可执行动作"],
  "weak_points_summary": "学生薄弱点简述",
  "days": [
    {
      "day": 1,
      "label": "课后第1天复习（YYYY-MM-DD）",
      "time": "10-20分钟",
      "type": "day1",
      "steps": [
        {
          "step_label": "⏱ 第1步（2-4分钟）",
          "title": "复习目标/复习聚焦",
          "items": [{"type": "body", "text": "..."}, {"type": "fill", "text": "...", "answer": "..."}]
        },
        {
          "step_label": "⏱ 第2步（4-8分钟）",
          "title": "全课覆盖清单+执行清单",
          "items": [{"type": "fill", "text": "...", "answer": "..."}]
        },
        {
          "step_label": "⏱ 第3步（4-8分钟）",
          "title": "填空主任务+选择辅助+知识点加练/口述卡片+课堂原话回放",
          "items": [{"type": "fill", "text": "...", "answer": "..."}]
        }
      ],
      "choices": [{"question": "选择题题干", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "answer": "A"}],
      "self_test_phrase": "出发口令：..."
    },
    {
      "day": 14,
      "label": "课后第14天复习（YYYY-MM-DD）",
      "time": "10-20分钟",
      "type": "daily",
      "items": [{"type": "body", "text": "..."}, {"type": "fill", "text": "...", "answer": "..."}],
      "choices": [{"question": "选择题题干", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "answer": "A"}],
      "self_test_phrase": "出发口令：..."
    }
  ],
  "knowledge_sections": {
    "第1天": [{"title": "知识点加练标题", "mixed": {"blanks": [["填空题____", "答案"]], "choices": [{"question": "...", "options": ["A. ...", "B. ..."], "answer": "A"}]}, "oral": {"prompts": ["老师追问"], "keypoints": ["回答要点"]}}]
  },
  "weekly_review_prompts": ["...", "...", "...", "..."]
}
"""

# ─── 复习风格附加提示词 ────────────────────────────────────────────────────────
PROMPT_STYLE_ADDONS = {
    "B": """
【三问法要求】
每个复习节点（第1/2/7/14/30天）的 items 内容必须围绕三个维度展开，三条填空分别对应：
① 是什么：清晰定义或描述该知识点（填空形式）
② 为什么：解释原理或背后的逻辑（填空形式）
③ 怎么用：给出具体的使用场景或做题步骤（填空形式）
例如：① 一次函数定义：自变量x的最高次数为____，且k____0
     ② k>0时图像递增，是因为____
     ③ 遇到"两点求解析式"：第一步____，第二步____
""",
    "C": """
【考题格式导向要求】
每个复习节点聚焦一种考题题型，填空内容呈现该题型的解题框架：
- 在 items 开头用 body 类型注明题型，如"📝 [填空题·斜率判断]"
- 后续填空直接对应解题步骤模板
- 最后一条填空指出该题型最常见的失分点，格式：⚠️ 易错点：____
例如：📝 [解答题·待定系数法]
看到"已知图像过两点" → 第一步必须____，第二步列____元方程组
⚠️ 易错点：____
""",
    "D": """
【对话自测要求】
每个复习节点用"老师提问→学生回答"的对话链呈现：
- body 类型 item 写老师的问题，fill 类型 item 写学生需要填写的答案
- 问题之间自然衔接，由浅入深，每个节点包含2-3轮对话
- 格式：老师问：[具体问题]？→ 你答：____
例如：
  {"type":"body","text":"👩‍🏫 老师问：一次函数 y=kx+b 中，k 的作用是什么？"}
  {"type":"fill","text":"→ 你答：k 表示____，决定图像____"}
  {"type":"body","text":"👩‍🏫 老师追问：如果 k<0，图像是什么走向？"}
  {"type":"fill","text":"→ 你答：从左____到右____（递____）"}
""",
    "E": """
【遗忘清单要求】
每个复习节点以"核查清单"形式呈现，不要普通填空，改为：
- 第一条 body 类型 item 写"✅ 今天快速核查，你还记得吗？"
- 后续每条 fill 类型 item 用"☐"开头，一句话描述一个关键点，末尾加【易错】或【常考】标注
- 每个节点列出3-5条，精准指向该天主题的核心记忆点
例如：
  {"type":"body","text":"✅ 今天快速核查，你还记得吗？"}
  {"type":"fill","text":"☐ k的符号决定图像____方向（____为正，____为负）【易错】"}
  {"type":"fill","text":"☐ b=0 时函数图像过____，叫____函数【常考】"}
""",
}


def _build_system_prompt(styles: list) -> str:
    """根据选中的风格列表，在基础提示词后追加附加要求。"""
    base = PLAN_SYSTEM_PROMPT
    if not styles:
        return base
    addon_parts = []
    style_names = {"B": "三问法", "C": "考题格式", "D": "对话自测", "E": "遗忘清单"}
    for s in styles:
        if s in PROMPT_STYLE_ADDONS:
            addon_parts.append(PROMPT_STYLE_ADDONS[s])
    if not addon_parts:
        return base
    names = "、".join(style_names.get(s, s) for s in styles if s in PROMPT_STYLE_ADDONS)
    header = f"\n\n【本次选用的教学风格：{names}】\n以下是各风格的具体要求，生成时需严格遵守："
    return base + header + "\n".join(addon_parts)


MONTHLY_SYSTEM_PROMPT = """你是一位专业的初中学科辅导老师。
你将收到本月全部课堂总结（多节课），需要生成一份月度综合复习计划 JSON。

【月度复习计划特点】
- 聚焦本月所有课程的核心知识点
- 优先处理多节课中反复出现的薄弱点
- 生成 14 天的每日复习安排（前2天总复盘，后面分知识板块）

【输出格式】与单节课相同，但：
- lesson_info.topic = "X月综合复习"
- key_categories 来自所有课程知识点的合并与提炼
- days 安排 14 天（day 1-2 为month_day1 类型，day 3-14 为daily类型）

只返回合法 JSON，不要额外说明。
"""


CONSULTATION_BATCH_SYSTEM_PROMPT = f"""你是咨询记录整理助手。
你只能输出 JSON，不要输出额外说明。

请把输入文本拆成 items 数组，每一项都必须是：
- action: 只能是 create 或 update
- target_id: 只有文本中明确出现记录 ID 时才允许填写整数，否则必须是 null
- reason: 简短说明判断依据
- fields: 只能包含以下字段中的一部分：
    date
    parent_wechat_name
    child_name
    grade
    receiving_teacher
    teacher_id
    consultation_subject
    need_detail
    source_channel
    source_channel_note
    screenshot
    follow_up_status
    follow_up_note
- warnings: 字符串数组

严格规则：
1. 只有文本中明确出现 ID 182、记录182、#182 这类显式记录 ID 时，action 才能是 update。
2. 没有显式记录 ID 时，必须输出 action=create 且 target_id=null。
3. 不要编造记录 ID。
4. 如果一段文本信息不足，可以保留 fields 的部分字段，不要补全虚构内容。
5. 如果填写 follow_up_status，值只能是：{"、".join(CONSULTATION_FOLLOW_UP_STATUS_OPTIONS)}。
6. 不要自造新的跟进状态，例如“待开课缴费”“已试听”“待确认缴费”这类都不能输出到 follow_up_status。
7. 如果原文只表达“继续联系”“后续再跟”这类模糊意思，但没有明确落到现有状态，就不要填写 follow_up_status。
8. 顶层返回 {{"items": [...], "warnings": [...]}}。
"""


# ─── 音频转录 ──────────────────────────────────────────────────────────────────
def transcribe_audio(audio_path: str, *, include_usage: bool = False):
    """使用本地 faster-whisper 转录音频文件，返回转录文本。"""
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"音频文件不存在：{audio_path}")
    
    supported = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac"}
    if audio_path.suffix.lower() not in supported:
        raise ValueError(f"不支持的音频格式：{audio_path.suffix}（支持：{', '.join(supported)}）")
    
    print(f"正在转录音频：{audio_path.name} ...")
    transcription = _transcribe_audio_path_locally(str(audio_path))
    print("转录完成。")
    if include_usage:
        return transcription, _local_whisper_usage_dict()
    return transcription


# ─── 课堂总结解析 ──────────────────────────────────────────────────────────────
def parse_and_generate_plan(
    summary_text: str,
    subject: str = "",
    grade: str = "",
    topic: str = "",
    weak_points: str = "",
    lesson_date: str = "",
    prompt_styles: list = None,
    include_usage: bool = False,
):
    """
    将自由格式课堂总结（文本）解析为结构化复习计划 JSON。
    返回 plan dict，可直接传入 pdf_engine 生成 PDF，或存入数据库。
    """
    client = _get_client()

    # 构建用户消息
    meta_parts = [f"生成日期（第0天）：{date.today().isoformat()}"]
    if subject:   meta_parts.append(f"科目：{subject}")
    if grade:     meta_parts.append(f"年级：{grade}")
    if topic:     meta_parts.append(f"本节课主题：{topic}")
    if weak_points: meta_parts.append(f"学生薄弱点：{weak_points}")
    if lesson_date: meta_parts.append(f"上课日期：{lesson_date}")
    
    meta_block = "\n".join(meta_parts)
    user_msg = f"{meta_block}\n\n课堂总结：\n{summary_text}"

    print("正在生成复习计划（AI处理中）...")
    system_prompt = _build_system_prompt(prompt_styles or [])
    response = client.chat.completions.create(
        model=_get_structured_generation_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    plan = _loads_model_json(raw)
    
    # 补充日期
    if lesson_date and "lesson_info" in plan:
        plan["lesson_info"]["date"] = lesson_date
    else:
        plan.setdefault("lesson_info", {}).setdefault("date", str(date.today()))
    
    print("复习计划生成完成。")
    if include_usage:
        return plan, _usage_dict(response)
    return plan


def parse_consultation_batch_text(raw_text: str, *, include_usage: bool = False):
    client = _get_client()
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": CONSULTATION_BATCH_SYSTEM_PROMPT},
            {"role": "user", "content": str(raw_text or "")},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    payload = _loads_model_json(response.choices[0].message.content)
    if not isinstance(payload.get("items"), list):
        raise RuntimeError("咨询记录批量解析返回了无效结果")
    parsed = {
        "items": payload.get("items", []),
        "warnings": payload.get("warnings", []),
    }
    if include_usage:
        return parsed, _usage_dict(response)
    return parsed


# ─── 月度复习计划聚合 ──────────────────────────────────────────────────────────
def generate_teacher_feedback_draft(
    *,
    lesson: dict,
    students: list[dict],
    custom_templates: list[dict],
    include_usage: bool = False,
):
    client = _get_client()
    plan_json = json.dumps(lesson.get("plan") or {}, ensure_ascii=False)
    student_block = json.dumps(
        {"students": students, "custom_templates": custom_templates},
        ensure_ascii=False,
    )
    system_prompt = (
        "你是一名负责生成家校沟通课后反馈的教研助理。"
        "输出纯文本，不要 Markdown，不要项目符号。"
        "每位学生输出四段：本周课堂重点、这节课的作用、课堂状态、家长配合建议。"
        "本周课堂重点必须控制在20个中文字符以内。"
        "“这节课的作用”要结合复习计划与课堂内容，识别它更偏向思维训练帮助，还是更偏向中考、小升初、高考等考试帮助，并用家校沟通口吻写清楚。"
        "“课堂状态”必须优先参考学生的 selected_template_label、selected_template_guidance 和 remark。"
        "“家长配合建议”必须结合 selected_template_guidance、remark 和复习计划给出可执行建议。"
        "每位学生都以“学生姓名：”开头。"
        "只输出已选择状态模板的学生，学生与学生之间空一行。"
    )
    user_prompt = (
        f"课程信息：{lesson.get('subject', '')} {lesson.get('grade', '')} {lesson.get('topic', '')}\n"
        f"课堂总结：{lesson.get('summary', '')}\n"
        f"复习计划JSON：{plan_json}\n"
        f"学生输入：{student_block}"
    )
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    merged_text = (response.choices[0].message.content or "").strip()
    if include_usage:
        return merged_text, _usage_dict(response)
    return merged_text

def generate_class_feedback_bundle(
    *,
    class_name: str,
    teacher_name: str,
    start_date: str,
    end_date: str,
    source_summary: str,
    stage_notes: dict,
    students: list[dict],
) -> dict:
    client = _get_client()
    recent_confirmed_summaries = stage_notes.get("recent_confirmed_class_summaries") or []
    has_student_baseline = any(student.get("previous_baseline") for student in students)
    cold_start_mode = not recent_confirmed_summaries and not has_student_baseline
    history_readiness_level = "L0" if cold_start_mode else "L1+"
    system_prompt = (
        "你是一位负责教培班级反馈的老师助理。"
        "请先完整阅读输入资料，再输出 JSON 对象。"
        '返回格式必须是 {"class_summary":"...","student_entries":[{"student_id":1,"name":"张三","text":"..."}]}。'
        "不要输出 Markdown，不要输出额外解释。"
        "学生反馈应只基于提供的阶段课次、课后反馈、阶段备注和历史基线。"
        "生成结果要像老师直接发给家长的消息，使用自然口吻，允许有温度、有观察感，但不要夸张。"
        "班级总评也要像老师发给家长群的消息，不要写成公文式总结。"
        "不要写成系统总结或阶段报告，不要使用过于生硬的分析腔。"
        "即使历史资料不足，也要保持老师对家长说话的拟人化表达。"
        "冷启动时，多写老师当下的课堂观察，像“这节课孩子愿意跟着往前走，只是一到完整句表达还是会卡一下”。"
        "也可以写“目前孩子在阅读定位上能跟住，接下来我会继续带着他把会做题慢慢过渡到能顺口表达出来”。"
        "班级总评少用“整体来看”“表现出一定不足”“能力提升”等抽象总结词，尽量改成老师会直接发在家长群里的自然说法。"
        "少用“整体来看”“表现出一定不足”“能力提升”等抽象总结词。"
        "只有在存在明确历史基线时，才允许使用“进步明显”“有点回落”“变化不大”等比较表达；"
        "如果没有明确历史基线，请改用当前阶段的客观观察。"
        "没有明确历史基线时，不要写“比上次”“相比之前”“延续前几周趋势”“和上阶段相比”等比较型说法。"
        "历史不足时，可以写“这节课/这几天孩子...”“目前孩子...”“接下来我会继续...”这类自然表达。"
    )
    user_prompt = json.dumps(
        {
            "class_name": class_name,
            "teacher_name": teacher_name,
            "start_date": start_date,
            "end_date": end_date,
            "cold_start_mode": cold_start_mode,
            "history_readiness_level": history_readiness_level,
            "source_summary": source_summary,
            "stage_notes": stage_notes,
            "students": students,
        },
        ensure_ascii=False,
    )
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    content = (response.choices[0].message.content or "").strip()
    bundle = _loads_model_json(content)
    if not isinstance(bundle, dict):
        raise ValueError("AI 返回格式不正确")
    if not isinstance(bundle.get("student_entries"), list):
        bundle["student_entries"] = []
    bundle["class_summary"] = str(bundle.get("class_summary") or "").strip()
    return bundle
def generate_monthly_plan(lessons, month_str: str, *, include_usage: bool = False):
    """
    给定本月所有 lesson 记录列表，生成月度综合复习计划。
    每个 lesson dict 应包含 summary、topic、subject、grade、weak_points 等字段。
    """
    client = _get_client()

    # 构建月度摘要
    parts = [f"月份：{month_str}\n共 {len(lessons)} 节课\n"]
    for i, lesson in enumerate(lessons, 1):
        parts.append(
            f"【第{i}课 {lesson.get('date','')}】\n"
            f"主题：{lesson.get('topic','')}\n"
            f"薄弱点：{lesson.get('weak_points','')}\n"
            f"总结摘要：{lesson.get('summary','')[:800]}\n"
        )
    combined = "\n---\n".join(parts)

    print(f"正在生成 {month_str} 月度复习计划（AI处理中）...")
    response = client.chat.completions.create(
        model=_get_structured_generation_model(),
        messages=[
            {"role": "system", "content": MONTHLY_SYSTEM_PROMPT},
            {"role": "user",   "content": combined},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    plan = _loads_model_json(response.choices[0].message.content)
    plan.setdefault("lesson_info", {})["month"] = month_str
    plan["lesson_info"]["topic"] = f"{month_str} 综合复习"
    print("月度复习计划生成完成。")
    if include_usage:
        return plan, _usage_dict(response)
    return plan
