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

    elif provider == "n1n":
        key = cfg.get("n1n_api_key", "") or os.environ.get("N1N_API_KEY", "")
        base_url = cfg.get("n1n_base_url", "https://api.n1n.ai/v1").strip()
        if not key:
            raise RuntimeError("未找到 N1N API Key，请在设置页面配置。")
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
    provider = str(cfg.get("vision_provider") or "n1n").strip() or "n1n"

    if provider == "n1n":
        key = cfg.get("n1n_api_key", "") or os.environ.get("N1N_API_KEY", "")
        base_url = cfg.get("n1n_base_url", "https://api.n1n.ai/v1").strip()
        if not key:
            raise RuntimeError("未找到 N1N API Key，请在设置页面配置。")
        return OpenAI(api_key=key, base_url=base_url)

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

    return _get_client()


def _get_chat_model() -> str:
    """返回当前服务商对应的对话模型名称。"""
    cfg = _load_config()
    provider = cfg.get("provider", "deepseek")
    if provider == "deepseek":
        return cfg.get("deepseek_model", "deepseek-chat")
    elif provider == "mimo":
        return cfg.get("mimo_model", "MiMo-7B-RL")
    elif provider == "n1n":
        return cfg.get("n1n_model", "gpt-4o")
    return "gpt-4o"


def _get_structured_generation_model() -> str:
    return str(_get_chat_model() or "deepseek-chat")


def _get_vision_model() -> str:
    return str(_load_config().get("vision_model") or "gpt-5.5")


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
你需要判断上传图片是否属于几何题或几何体题，并为非几何题提取可直接进入错题库的题目文本。
题目文本允许“正文 + LaTeX 公式”混合输出：
- 普通中文、英文和题干说明直接输出为普通文本
- 行内公式使用 $...$
- 独立成行的公式使用 $$...$$
- 在 JSON 字符串里，LaTeX 命令的反斜杠必须写成双反斜杠，例如 \\frac、\\text、\\to
- 不要把整道题都改写成纯 LaTeX，只把公式片段转成 LaTeX
如果能明确识别公式结构，优先输出可渲染的 LaTeX；如果某个符号拿不准，宁可保留原始可读文本，也不要编造错误公式。
只返回 JSON，不要输出额外解释。
返回字段必须包含：
- is_geometry: boolean
- question_text: string
- confidence: string
- notes: string
如果是几何题，question_text 返回空字符串。
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

请用纯文本返回，不要返回 JSON。
第一行必须是“结论：通过”或“结论：不通过”。
如果不通过，后续写明问题和修改要求，方便下一轮重写。"""

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

严格规则：
1. 不要直接给出原题答案，不要提示孩子该怎样把这道题一步一步做对。
2. 生成内容主要依据孩子自述错因、顶层错因分类和补充备注；题目内容只用于确认错因语境，不要把重点放在讲题上。
3. 不要单独生成“下次提醒”或类似的第三个提示框；所有辅助都必须融进上面两个书写区里。
4. 不要把两个书写区的小标题固定成“把错因补完整”“写一写以后怎么做”等统一模板，要根据每题错因自然生成。
5. 两个书写区都要以挖空题为主，不要把其中任何一个写成纯叙述、开放作文题或老师提示语。
6. reason_blank_prompt 聚焦“这题为什么错”，但不要把孩子没说过或题目里没明确给出的细节硬写成确定事实；如果信息不足，就用“条件、关键词、知识点、检查顺序、计算步骤”这类通用说法轻轻引导。
7. improvement_summary_prompt 聚焦“接下来怎么补、以后先提醒自己什么”，仍然要写成挖空题，不要变成解题教学，也不要替孩子把计划写得过满过细。
8. 每个书写区正文控制在 1 到 2 句，2 到 3 个 ______ 空格即可；不要为了凑空格写成长段反思。
9. 不要在挖空题后面再追加纯写字线、自由总结、长段说明或“请写一写”的作文式提示。
10. 如果是细节问题，优先围绕检查顺序、符号、单位、抄写和验算来轻量组织提示。
11. 如果是审题问题，优先围绕看清条件、关键词和已知信息来轻量组织提示。
12. 如果是方法问题，优先围绕先判断方法是否合适、有没有用对思路来轻量组织提示。
13. 如果是知识点问题，优先围绕先回忆规则、定义或判断依据，再写一句接下来怎么补。
14. 句子要自然，适合小学/初中学生抄写和填写，不要出现工程术语。
15. title 控制在 8 到 24 个字。"""

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

    if is_geometry:
        return {
            "is_geometry": True,
            "question_text": "",
            "confidence": confidence,
            "notes": notes,
        }

    normalized_text = _repair_wrong_question_latex_transport(question_text)
    normalized_text = normalized_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_text = "\n".join(line.strip() for line in normalized_text.split("\n")).strip()
    normalized_text = re.sub(r"\n{3,}", "\n\n", normalized_text)
    compact_text = re.sub(r"\s+", "", normalized_text)
    if normalized_text in _WRONG_QUESTION_TEXT_FAILURE_MARKERS or len(compact_text) < 6:
        raise ValueError("题目识别失败，请重新识别")

    return {
        "is_geometry": False,
        "question_text": normalized_text,
        "confidence": confidence,
        "notes": notes,
    }


def _request_wrong_question_recognition_attempt(
    image_url: str,
    *,
    revision_feedback: str = "",
    client=None,
) -> dict:
    active_client = client or _get_vision_client()
    user_instruction = "请判断这道错题是否属于几何题，并提取非几何题题目文本。"
    if revision_feedback:
        user_instruction = (
            "上一版识别没有通过质量检查。请根据下面的审稿意见重新识别并重写题目文本：\n"
            f"{revision_feedback}\n\n"
            "只保留原始题目主体，忽略学生手写答案、草稿、订正、批改痕迹和解题过程。"
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


def _normalize_wrong_question_practice_sheet_material(payload: dict, *, expected_record_ids: list[str]) -> dict:
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
        ai_hint = str(source.get("ai_hint") or "").strip()
        reason_blank_prompt = str(source.get("reason_blank_prompt") or "").strip()
        improvement_summary_prompt = str(source.get("improvement_summary_prompt") or "").strip()

        reason_blank_prompt = reason_blank_prompt.replace("\r\n", "\n").replace("\r", "\n").strip()
        improvement_summary_prompt = improvement_summary_prompt.replace("\r\n", "\n").replace("\r", "\n").strip()

        reason_lines = [line.strip() for line in reason_blank_prompt.split("\n") if line.strip()]
        improvement_lines = [line.strip() for line in improvement_summary_prompt.split("\n") if line.strip()]

        if reason_lines:
            if len(reason_lines) >= 2:
                reason_title = reason_lines[0]
                reason_body = "\n".join(reason_lines[1:])
            else:
                reason_title = ""
                reason_body = reason_lines[0]
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
                improvement_summary_prompt = f"{improvement_title}\n{improvement_body}".strip()
            else:
                improvement_summary_prompt = improvement_lines[0]

        if not wrong_question_record_id or not reason_blank_prompt or not improvement_summary_prompt:
            raise ValueError("wrong question practice sheet generation failed")

        normalized_items.append(
            {
                "wrong_question_record_id": wrong_question_record_id,
                "ai_hint": ai_hint,
                "reason_blank_prompt": reason_blank_prompt,
                "improvement_summary_prompt": improvement_summary_prompt,
            }
        )

    normalized_record_ids = [item["wrong_question_record_id"] for item in normalized_items]
    if normalized_record_ids != expected_record_ids:
        raise ValueError("wrong question practice sheet generation failed")

    return {
        "title": title,
        "items": normalized_items,
    }


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
        normalized_items.append(
            {
                "wrong_question_record_id": str(item.get("wrong_question_record_id") or "").strip(),
                "question_order": int(item.get("question_order") or 0),
                "is_geometry": bool(item.get("is_geometry")),
                "question_text": str(item.get("question_text_snapshot") or "").strip(),
                "child_reason_text": str(item.get("child_reason_text_snapshot") or "").strip(),
                "primary_error_type": str(item.get("primary_error_type_snapshot") or "").strip(),
                "cause_note": str(item.get("cause_note_snapshot") or "").strip(),
            }
        )

    client = _get_client()
    response = client.chat.completions.create(
        model=_get_structured_generation_model(),
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
    normalized = _normalize_wrong_question_practice_sheet_material(
        payload,
        expected_record_ids=expected_record_ids,
    )
    if include_usage:
        return normalized, _usage_dict(response)
    return normalized


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
      "self_test_phrase": "出发口令：..."
    },
    {
      "day": 14,
      "label": "课后第14天复习（YYYY-MM-DD）",
      "time": "10-20分钟",
      "type": "daily",
      "items": [{"type": "body", "text": "..."}, {"type": "fill", "text": "...", "answer": "..."}],
      "self_test_phrase": "出发口令：..."
    }
  ],
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
