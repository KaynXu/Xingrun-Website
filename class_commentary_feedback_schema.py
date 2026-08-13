from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from class_commentary import (
    CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4,
    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
    normalize_class_commentary_feedback_text,
)


CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1 = "class_commentary.student_feedback.v1"
CLASS_COMMENTARY_STUDENT_NAME_MATCHER_V1 = "class_commentary.student_name_matcher.v1"
CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1 = "class_commentary.attending_roster_scope.v1"
CLASS_COMMENTARY_STRUCTURED_RESPONSE_FORMAT = {"type": "json_object"}
CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_DISABLED_V1 = "disabled_v1"
CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2 = "isolated_v2"
CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3 = "batch_isolated_v3"
CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V1 = (
    "class_commentary.student_evidence_matcher.v1"
)
CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2 = (
    "class_commentary.student_evidence_fail_closed.v2"
)
CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT = 2000
CLASS_COMMENTARY_STUDENT_FEEDBACK_TOTAL_LIMIT = 30000
CLASS_COMMENTARY_SPARSE_FEEDBACK_MIN_LEXICAL_CHARS = 12
CLASS_COMMENTARY_RICH_FEEDBACK_MIN_LEXICAL_CHARS = 36
CLASS_COMMENTARY_RICH_EVIDENCE_MIN_LEXICAL_CHARS = 24


_WECHAT_EMOJI_TOKEN_NAMES = frozenset(
    {
        "OK",
        "NO",
        "亲亲",
        "偷笑",
        "傲慢",
        "再见",
        "冷汗",
        "加油",
        "发呆",
        "发怒",
        "可怜",
        "呲牙",
        "咒骂",
        "坏笑",
        "奋斗",
        "委屈",
        "害羞",
        "尴尬",
        "强",
        "微笑",
        "心碎",
        "惊恐",
        "惊讶",
        "愉快",
        "憨笑",
        "抓狂",
        "抱拳",
        "合十",
        "爱心",
        "拥抱",
        "捂脸",
        "握手",
        "撇嘴",
        "敲打",
        "流汗",
        "流泪",
        "月亮",
        "玫瑰",
        "疑问",
        "白眼",
        "破涕为笑",
        "礼物",
        "糗大了",
        "胜利",
        "转圈",
        "调皮",
        "鄙视",
        "闭嘴",
        "难过",
        "哇",
        "好的",
        "社会社会",
        "鼓掌",
    }
)
_WECHAT_EMOJI_TOKEN_PATTERN = re.compile(r"\[([^\[\]\r\n]{1,8})\]")
_EMOJI_OCCASIONAL_CUES = (
    "偶尔",
    "轻量",
    "少量",
    "可放在",
    "可以放在",
    "可用于",
    "可以用于",
    "按需使用",
    "视情况使用",
    "rarely",
    "lightly",
    "sparing",
    "optional",
    "when appropriate",
    "do not overuse",
    "don't overuse",
    "不要过用",
    "不要多用",
    "不要堆满",
    "不可堆满",
)
_EMOJI_NORMAL_CUES = (
    "常用表情",
    "常用 emoji",
    "常用emoji",
    "表情占位符",
    "emoji habits",
    "emoji system",
)
_GENERIC_FEEDBACK_PHRASES = (
    "继续努力",
    "继续加油",
    "保持状态",
    "再接再厉",
    "相信你会越来越好",
    "相信你会越来越棒",
    "期待你更好的表现",
)


_PROBLEM_CUES = (
    "不够",
    "不会",
    "不熟",
    "不清楚",
    "不完整",
    "不规范",
    "出错",
    "困难",
    "忘记",
    "欠缺",
    "卡住",
    "混淆",
    "粗心",
    "漏掉",
    "漏写",
    "不稳定",
    "不扎实",
    "不准确",
    "不到位",
    "没写",
    "错误",
    "薄弱",
    "走神",
    "需要改进",
    "需要加强",
    "需要检查",
    "需要注意",
)
_ACTION_VERBS = tuple(
    sorted(
        {
            "复习",
            "练习",
            "验算",
            "检查",
            "整理",
            "订正",
            "重做",
            "完成",
            "记录",
            "记",
            "圈出",
            "标注",
            "勾画",
            "写出",
            "说出",
            "讲解",
            "讲清",
            "讲",
            "总结",
            "背诵",
            "抽背",
            "默写",
            "朗读",
            "阅读",
            "预习",
            "回看",
            "看",
            "对照",
            "拆分",
            "列式",
            "画图",
            "计算",
            "口算",
            "复盘",
            "提问",
            "找出",
            "尝试",
            "做",
            "补",
            "巩固",
        },
        key=len,
        reverse=True,
    )
)
_ACTION_DIRECTIVE_CUES = (
    "建议",
    "接下来",
    "下一步",
    "记得",
    "别忘",
    "试着",
    "请",
    "可以",
    "课后",
    "回家",
    "下去",
    "每天",
    "今晚",
    "明天",
    "本周",
    "下次",
    "后面",
    "之后",
    "后续",
    "以后",
    "务必",
    "一定",
    "多",
    "继续",
)
_ACTION_OBJECT_ANCHORS = (
    "分钟",
    "步骤",
    "符号",
    "错题",
    "例题",
    "题目",
    "这题",
    "题干",
    "概念",
    "公式",
    "知识点",
    "草稿",
    "作业",
    "笔记",
    "过程",
    "答案",
    "单位",
    "关键词",
    "道题",
    "遍",
    "次",
    "页",
)
_INTRINSIC_ACTION_VERBS = {
    "验算",
    "订正",
    "重做",
    "圈出",
    "标注",
    "列式",
    "画图",
    "口算",
    "背诵",
    "默写",
    "朗读",
    "预习",
    "复盘",
    "提问",
    "抽背",
    "勾画",
}

_TEACHER_FOLLOW_UP_ACTION_PATTERN = re.compile(
    r"(?:明天|下次|后面|之后|后续|接下来|本周|以后)"
    r".{0,16}(?:我|老师)?(?:还|会|要|再)?.{0,8}"
    r"(?:重点看|检查|抽查|验收|提问|考查|考一考|讲解|专门拿出来讲|再讲)"
)
_STUDENT_DIRECT_ACTION_PATTERN = re.compile(
    r"(?:需要|要)(?:你|娃娃|孩子|学生)?.{0,6}(?:把|将)"
    r".{0,24}(?:复习|练习|验算|检查|整理|订正|重做|完成|记录|记|圈出|"
    r"标注|勾画|写出|说出|讲清|总结|背诵|抽背|默写|朗读|阅读|预习|"
    r"回看|看|对照|拆分|列式|画图|计算|口算|复盘|提问|找出|尝试|做|补|巩固)"
    r"|需要(?:加强|加大|坚持).{0,16}(?:抽背|练习|复习|验算|检查|整理|订正|巩固)"
)


class ClassCommentaryStudentScopeError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ClassCommentaryStructuredFeedbackValidationError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        student_id: int | None = None,
        field: str = "",
        limit: int | None = None,
        reason: str = "",
    ):
        super().__init__(reason or code)
        self.code = code
        self.student_id = student_id
        self.field = field
        self.limit = limit
        self.reason = reason or code


class _StudentFeedbackItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    student_id: StrictInt
    feedback_text: StrictStr


class _StudentFeedbackEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1]
    items: list[_StudentFeedbackItemV1]


class _StudentGraphEvidenceRefsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    student_id: StrictInt
    evidence_refs: list[StrictStr]


class _BatchIsolatedStudentFeedbackEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1]
    items: list[_StudentFeedbackItemV1]
    used_graph_evidence_refs_by_student: list[_StudentGraphEvidenceRefsV1]


def _invalid_envelope(
    *,
    schema_version: str,
    stored_hash: str,
    derived_text: str,
) -> dict:
    return {
        "feedback_schema_version": schema_version,
        "feedback_schema_status": "invalid",
        "student_feedback_items": [],
        "structured_feedback_hash": stored_hash,
        "derived_feedback_text": derived_text,
        "writable": False,
    }


def _parse_json(value: object):
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value or ""))


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_match_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip()
    return re.sub(r"\s+", " ", normalized)


def _match_normalized_student_name_spans(
    text: str,
    normalized_roster: list[tuple[int, int, str]],
) -> list[tuple[int, int, int]]:
    candidates: list[tuple[int, int, int, int]] = []
    for position, student_id, student_name in normalized_roster:
        start = text.find(student_name)
        while start >= 0:
            candidates.append((start, start + len(student_name), position, student_id))
            start = text.find(student_name, start + 1)

    accepted_spans: list[tuple[int, int, int]] = []
    for start, end, _, student_id in sorted(
        candidates,
        key=lambda item: (-(item[1] - item[0]), item[0], item[2]),
    ):
        if any(
            start < accepted_end and end > accepted_start
            for accepted_start, accepted_end, _ in accepted_spans
        ):
            continue
        accepted_spans.append((start, end, student_id))
    return accepted_spans


def _normalize_class_commentary_scope_roster(
    roster: object,
) -> list[tuple[int, int, str]]:
    if not isinstance(roster, list):
        raise ValueError("structured feedback roster must be a list")
    normalized_roster: list[tuple[int, int, str]] = []
    names_seen: set[str] = set()
    student_ids_seen: set[int] = set()
    for position, item in enumerate(roster):
        if not isinstance(item, Mapping):
            raise ValueError("structured feedback roster item is invalid")
        student_id = item.get("student_id")
        student_name = _normalize_match_text(item.get("student_name"))
        if type(student_id) is not int or student_id <= 0 or student_id in student_ids_seen:
            raise ValueError("structured feedback roster item is invalid")
        if not student_name:
            raise ValueError("structured feedback roster name is invalid")
        if student_name in names_seen:
            raise ClassCommentaryStudentScopeError("student_roster_name_ambiguous")
        student_ids_seen.add(student_id)
        names_seen.add(student_name)
        normalized_roster.append((position, student_id, student_name))
    return normalized_roster


def match_class_commentary_eligible_student_ids(
    *,
    transcript_text: object,
    roster: object,
) -> list[int]:
    normalized_roster = _normalize_class_commentary_scope_roster(roster)

    transcript = _normalize_match_text(transcript_text)
    accepted_ids = {
        student_id
        for _, _, student_id in _match_normalized_student_name_spans(
            transcript,
            normalized_roster,
        )
    }

    eligible_ids = [
        student_id
        for _, student_id, _ in normalized_roster
        if student_id in accepted_ids
    ]
    if not eligible_ids:
        raise ClassCommentaryStudentScopeError("student_feedback_no_eligible_students")
    return eligible_ids


def resolve_class_commentary_attending_roster_student_ids(
    *,
    roster: object,
) -> list[int]:
    normalized_roster = _normalize_class_commentary_scope_roster(roster)
    eligible_ids = [student_id for _, student_id, _ in normalized_roster]
    if not eligible_ids:
        raise ClassCommentaryStudentScopeError("student_feedback_no_eligible_students")
    return eligible_ids


def build_class_commentary_eligible_scope_hash(
    *,
    transcript_hash: str,
    roster_hash: str,
    eligible_student_ids: list[int],
    matcher_version: str = CLASS_COMMENTARY_STUDENT_NAME_MATCHER_V1,
) -> str:
    envelope = {
        "attending_roster_hash": str(roster_hash or ""),
        "confirmed_transcript_hash": str(transcript_hash or ""),
        "eligible_student_ids": eligible_student_ids,
        "student_mention_matcher_version": str(matcher_version or ""),
    }
    return _content_hash(_canonical_json(envelope))


def _parse_frozen_scope(generation: Mapping[str, object]) -> tuple[list[int], dict[int, str]]:
    roster = _parse_json(generation.get("attending_roster_snapshot_json"))
    eligible_ids = _parse_json(generation.get("eligible_student_ids_json"))
    if not isinstance(roster, list) or not isinstance(eligible_ids, list) or not eligible_ids:
        raise ValueError("structured feedback frozen scope is invalid")

    roster_order: list[int] = []
    names_by_id: dict[int, str] = {}
    for item in roster:
        if not isinstance(item, dict):
            raise ValueError("structured feedback frozen roster is invalid")
        student_id = item.get("student_id")
        student_name = item.get("student_name")
        if (
            type(student_id) is not int
            or student_id <= 0
            or not isinstance(student_name, str)
            or not student_name.strip()
            or student_id in names_by_id
        ):
            raise ValueError("structured feedback frozen roster is invalid")
        roster_order.append(student_id)
        names_by_id[student_id] = student_name

    parsed_eligible_ids: list[int] = []
    for student_id in eligible_ids:
        if (
            type(student_id) is not int
            or student_id <= 0
            or student_id in parsed_eligible_ids
            or student_id not in names_by_id
        ):
            raise ValueError("structured feedback eligible scope is invalid")
        parsed_eligible_ids.append(student_id)
    if [student_id for student_id in roster_order if student_id in parsed_eligible_ids] != parsed_eligible_ids:
        raise ValueError("structured feedback eligible scope order is invalid")
    return parsed_eligible_ids, names_by_id


def validate_class_commentary_structured_generation_contract(
    generation: Mapping[str, object],
) -> None:
    if str(generation.get("feedback_schema_version") or "") != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1:
        raise ValueError("structured feedback schema contract is invalid")
    snapshot_hash_fields = (
        ("confirmed_transcript_snapshot", "confirmed_transcript_hash"),
        ("attending_roster_snapshot_json", "attending_roster_hash"),
        ("skill_content_snapshot", "skill_content_hash"),
    )
    if any(
        _content_hash(str(generation.get(snapshot_field) or ""))
        != str(generation.get(hash_field) or "")
        for snapshot_field, hash_field in snapshot_hash_fields
    ):
        raise ValueError("structured feedback core snapshot hash is invalid")
    eligible_ids, names_by_id = _parse_frozen_scope(generation)
    matcher_version = str(generation.get("student_mention_matcher_version") or "")
    prompt_version = str(generation.get("prompt_version") or "")
    contract_pair = (matcher_version, prompt_version)
    if contract_pair == (
        CLASS_COMMENTARY_STUDENT_NAME_MATCHER_V1,
        CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
    ):
        pass
    elif contract_pair in {
        (
            CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1,
            CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
        ),
        (
            CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1,
            CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
        ),
    }:
        if eligible_ids != list(names_by_id):
            raise ValueError("structured feedback attending roster scope is invalid")
        if not bool(generation.get("attending_roster_explicit")):
            raise ValueError("structured feedback attending roster scope must be explicit")
    elif contract_pair in {
        (
            CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V1,
            CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
        ),
        (
            CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
            CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
        ),
    }:
        if eligible_ids != list(names_by_id):
            raise ValueError("isolated feedback attending roster scope is invalid")
        if not bool(generation.get("attending_roster_explicit")):
            raise ValueError("isolated feedback attending roster scope must be explicit")
    elif contract_pair == (
        CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1,
        CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4,
    ):
        if eligible_ids != list(names_by_id):
            raise ValueError("batch isolated feedback attending roster scope is invalid")
        if not bool(generation.get("attending_roster_explicit")):
            raise ValueError(
                "batch isolated feedback attending roster scope must be explicit"
            )
    else:
        raise ValueError("structured feedback prompt and scope contract is invalid")
    response_format = _parse_json(generation.get("response_format_json"))
    if response_format != CLASS_COMMENTARY_STRUCTURED_RESPONSE_FORMAT:
        raise ValueError("structured feedback response format contract is invalid")
    expected_memory_mode = (
        CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
        if prompt_version == CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2
        else CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
        if prompt_version == CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4
        else CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_DISABLED_V1
    )
    if str(generation.get("student_history_memory_mode") or "") != expected_memory_mode:
        raise ValueError("structured feedback memory contract is invalid")
    expected_scope_hash = build_class_commentary_eligible_scope_hash(
        transcript_hash=str(generation.get("confirmed_transcript_hash") or ""),
        roster_hash=str(generation.get("attending_roster_hash") or ""),
        eligible_student_ids=eligible_ids,
        matcher_version=matcher_version,
    )
    if str(generation.get("eligible_student_scope_hash") or "") != expected_scope_hash:
        raise ValueError("structured feedback eligible scope hash is invalid")


def _only_student_name_and_punctuation(text: str, student_name: str) -> bool:
    normalized_text = _normalize_match_text(text)
    normalized_name = _normalize_match_text(student_name)
    if normalized_name:
        normalized_text = normalized_text.replace(normalized_name, "")
    return not any(
        not char.isspace()
        and not unicodedata.category(char).startswith("P")
        and not unicodedata.category(char).startswith("S")
        for char in normalized_text
    )


def _is_emoji_base(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x1F000 <= codepoint <= 0x1FAFF
        or codepoint
        in {
            0x231A,
            0x231B,
            *range(0x23E9, 0x23F4),
            *range(0x23F8, 0x23FB),
            0x25AA,
            0x25AB,
            0x25FB,
            0x25FC,
            0x25FE,
            0x25FF,
            0x2614,
            0x2615,
            *range(0x2648, 0x2654),
            0x267F,
            0x2693,
            0x26A1,
            0x26AA,
            0x26AB,
            0x26BD,
            0x26BE,
            0x26C4,
            0x26C5,
            0x26CE,
            0x26D4,
            0x26EA,
            0x26F2,
            0x26F3,
            0x26F5,
            0x26FA,
            0x26FD,
            0x2705,
            0x270A,
            0x270B,
            0x2728,
            0x274C,
            0x274E,
            *range(0x2753, 0x2756),
            0x2757,
            *range(0x2795, 0x2798),
            0x27B0,
            0x27BF,
        }
    )


def _unicode_emoji_tokens(value: object) -> tuple[str, ...]:
    text = str(value or "")
    index = 0
    tokens: list[str] = []
    while index < len(text):
        start = index
        character = text[index]
        codepoint = ord(character)
        if character in "#*0123456789":
            cursor = index + 1
            if cursor < len(text) and ord(text[cursor]) == 0xFE0F:
                cursor += 1
            if cursor < len(text) and ord(text[cursor]) == 0x20E3:
                tokens.append(text[start : cursor + 1])
                index = cursor + 1
                continue
        if 0x1F1E6 <= codepoint <= 0x1F1FF:
            index += 1
            if index < len(text) and 0x1F1E6 <= ord(text[index]) <= 0x1F1FF:
                index += 1
            tokens.append(text[start:index])
            continue
        if not _is_emoji_base(character):
            if (
                (0x2600 <= codepoint <= 0x27BF or codepoint in {0x00A9, 0x00AE})
                and index + 1 < len(text)
                and ord(text[index + 1]) == 0xFE0F
            ):
                tokens.append(text[start : index + 2])
                index += 2
                continue
            index += 1
            continue
        index += 1
        while index < len(text) and (
            ord(text[index]) in {0xFE0E, 0xFE0F}
            or 0x1F3FB <= ord(text[index]) <= 0x1F3FF
        ):
            index += 1
        while index < len(text) and ord(text[index]) == 0x200D:
            index += 1
            if index >= len(text):
                break
            index += 1
            while index < len(text) and (
                ord(text[index]) in {0xFE0E, 0xFE0F}
                or 0x1F3FB <= ord(text[index]) <= 0x1F3FF
            ):
                index += 1
        tokens.append(text[start:index])
    return tuple(tokens)


def _emoji_token_count(value: object) -> int:
    text = str(value or "")
    return sum(
        1
        for match in _WECHAT_EMOJI_TOKEN_PATTERN.finditer(text)
        if match.group(1) in _WECHAT_EMOJI_TOKEN_NAMES
    ) + len(_unicode_emoji_tokens(text))


def _skill_emoji_style(
    value: object,
) -> tuple[str, frozenset[str], frozenset[str]]:
    text = str(value or "")
    normalized_text = unicodedata.normalize("NFKC", text).casefold()
    bracket_tokens = frozenset(
        match.group(1)
        for match in _WECHAT_EMOJI_TOKEN_PATTERN.finditer(text)
        if match.group(1) in _WECHAT_EMOJI_TOKEN_NAMES
    )
    unicode_tokens = frozenset(_unicode_emoji_tokens(text))
    if any(cue in normalized_text for cue in _EMOJI_OCCASIONAL_CUES):
        density = "occasional"
    elif any(
        re.search(pattern, normalized_text)
        for pattern in (
            r"(?:emoji|表情).{0,10}(?:频繁|高频|大量)",
            r"(?:频繁|高频|大量).{0,10}(?:emoji|表情)",
        )
    ):
        density = "frequent"
    elif (
        any(cue in normalized_text for cue in _EMOJI_NORMAL_CUES)
        or re.search(r"常用\s*(?:\[[^\]\r\n]{1,8}\]|[\U0001F000-\U0001FAFF])", text)
        or len(bracket_tokens) + len(unicode_tokens) >= 2
    ):
        density = "normal"
    else:
        density = "occasional"
    return density, bracket_tokens, unicode_tokens


def _feedback_skill_emoji_count(
    value: object,
    *,
    allowed_bracket_tokens: frozenset[str],
    allowed_unicode_tokens: frozenset[str],
) -> int:
    text = str(value or "")
    bracket_count = sum(
        1
        for match in _WECHAT_EMOJI_TOKEN_PATTERN.finditer(text)
        if match.group(1) in allowed_bracket_tokens
    )
    unicode_count = sum(
        1
        for token in _unicode_emoji_tokens(text)
        if token in allowed_unicode_tokens
    )
    return bracket_count + unicode_count


def _skill_declares_concrete_emoji_family(
    value: object,
    *,
    allowed_bracket_tokens: frozenset[str],
    allowed_unicode_tokens: frozenset[str],
) -> bool:
    text = str(value or "")
    normalized_text = unicodedata.normalize("NFKC", text).casefold()
    cue_positions = [
        normalized_text.find(cue)
        for cue in (*_EMOJI_OCCASIONAL_CUES, *_EMOJI_NORMAL_CUES)
        if cue in normalized_text
    ]
    for cue_position in cue_positions:
        window = text[max(0, cue_position - 160) : cue_position + 560]
        if _feedback_skill_emoji_count(
            window,
            allowed_bracket_tokens=allowed_bracket_tokens,
            allowed_unicode_tokens=allowed_unicode_tokens,
        ):
            return True
    return False


def _lexical_character_count(value: object) -> int:
    return sum(
        1
        for character in str(value or "")
        if unicodedata.category(character).startswith(("L", "N"))
    )


def _feedback_paragraphs(value: object) -> list[str]:
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n[ \t]*\n+", str(value or "").strip())
        if paragraph.strip()
    ]


def _has_concrete_next_action(value: object) -> bool:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[\n。！？!?；;.]+", str(value or ""))
        if sentence.strip()
    ]
    for sentence in sentences:
        if (
            _TEACHER_FOLLOW_UP_ACTION_PATTERN.search(sentence)
            or _STUDENT_DIRECT_ACTION_PATTERN.search(sentence)
        ):
            return True
        for verb in _ACTION_VERBS:
            for match in re.finditer(re.escape(verb), sentence):
                prefix = sentence[:match.start()]
                if not any(cue in prefix for cue in _ACTION_DIRECTIVE_CUES):
                    continue
                if (
                    verb in _INTRINSIC_ACTION_VERBS
                    or any(anchor in sentence for anchor in _ACTION_OBJECT_ANCHORS)
                ):
                    return True
                tail = sentence[match.end():]
                tail = re.sub(
                    r"(?:一下|一些|一点|一做|多|再|继续|认真|好好|及时|主动|起来|看看|加油)",
                    "",
                    tail,
                )
                if _lexical_character_count(tail) >= 2:
                    return True
    return False


def _v4_evidence_by_student(
    generation: Mapping[str, object],
    eligible_ids: list[int],
    names_by_id: Mapping[int, str],
) -> dict[int, list[str]]:
    raw_memory_context = generation.get("memory_context_snapshot_json")
    try:
        memory_context = _parse_json(raw_memory_context)
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="frozen batch quality context is invalid",
        ) from exc
    if (
        not isinstance(memory_context, Mapping)
        or memory_context.get("schema_version")
        != "class_commentary.batch_isolated_context.v1"
        or memory_context.get("student_history_memory_mode")
        != CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
        or _content_hash(_canonical_json(memory_context))
        != str(generation.get("memory_context_hash") or "")
    ):
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="frozen batch quality context is invalid",
        )
    partitions = (
        memory_context.get("student_contexts_by_id")
        if isinstance(memory_context, Mapping)
        else None
    )
    if not isinstance(partitions, list):
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="frozen batch quality context is invalid",
        )
    evidence_by_student: dict[int, list[str]] = {}
    for partition in partitions:
        if not isinstance(partition, Mapping):
            raise ClassCommentaryStructuredFeedbackValidationError(
                "structured_feedback_invalid",
                reason="frozen batch quality context is invalid",
            )
        student_id = partition.get("student_id")
        evidence_snapshot = partition.get("current_evidence_snapshot")
        fragments = (
            evidence_snapshot.get("fragments")
            if isinstance(evidence_snapshot, Mapping)
            else None
        )
        if (
            type(student_id) is not int
            or student_id not in names_by_id
            or student_id in evidence_by_student
            or not isinstance(fragments, list)
        ):
            raise ClassCommentaryStructuredFeedbackValidationError(
                "structured_feedback_invalid",
                student_id=student_id if type(student_id) is int else None,
                reason="frozen batch quality context is invalid",
            )
        useful_fragments: list[str] = []
        seen_hashes: set[str] = set()
        for fragment in fragments:
            if not isinstance(fragment, Mapping):
                raise ClassCommentaryStructuredFeedbackValidationError(
                    "structured_feedback_invalid",
                    student_id=student_id,
                    reason="frozen batch quality context is invalid",
                )
            text = str(fragment.get("text") or "").strip()
            text_hash = str(fragment.get("text_hash") or "")
            if not text or not text_hash or _content_hash(text) != text_hash:
                raise ClassCommentaryStructuredFeedbackValidationError(
                    "structured_feedback_invalid",
                    student_id=student_id,
                    reason="frozen batch quality context is invalid",
                )
            evidence_without_name = _normalize_match_text(text).replace(
                _normalize_match_text(names_by_id[student_id]),
                "",
            )
            if (
                text_hash not in seen_hashes
                and _lexical_character_count(evidence_without_name) >= 4
            ):
                seen_hashes.add(text_hash)
                useful_fragments.append(evidence_without_name)
        evidence_by_student[student_id] = useful_fragments
    if set(evidence_by_student) != set(eligible_ids):
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="frozen batch quality context scope is invalid",
        )
    return evidence_by_student


def _validate_v4_initial_feedback_quality(
    *,
    generation: Mapping[str, object],
    eligible_ids: list[int],
    names_by_id: Mapping[int, str],
    items_by_id: Mapping[int, str],
) -> None:
    emoji_density, allowed_bracket_tokens, allowed_unicode_tokens = _skill_emoji_style(
        generation.get("skill_content_snapshot")
    )
    declares_concrete_emoji_family = _skill_declares_concrete_emoji_family(
        generation.get("skill_content_snapshot"),
        allowed_bracket_tokens=allowed_bracket_tokens,
        allowed_unicode_tokens=allowed_unicode_tokens,
    )
    evidence_by_student = _v4_evidence_by_student(
        generation,
        eligible_ids,
        names_by_id,
    )
    total_skill_emoji_count = 0
    for student_id in eligible_ids:
        feedback_text = items_by_id[student_id]
        evidence_fragments = evidence_by_student[student_id]
        evidence_lexical_chars = sum(
            _lexical_character_count(evidence) for evidence in evidence_fragments
        )
        rich_evidence = (
            len(evidence_fragments) >= 2
            or evidence_lexical_chars
            >= CLASS_COMMENTARY_RICH_EVIDENCE_MIN_LEXICAL_CHARS
        )
        evidence_has_problem = any(
            cue in evidence
            for evidence in evidence_fragments
            for cue in _PROBLEM_CUES
        )
        required_emoji_count = (
            2
            if emoji_density == "frequent" and rich_evidence
            else 1
            if emoji_density in {"normal", "frequent"}
            else 0
        )
        feedback_skill_emoji_count = _feedback_skill_emoji_count(
            feedback_text,
            allowed_bracket_tokens=allowed_bracket_tokens,
            allowed_unicode_tokens=allowed_unicode_tokens,
        )
        total_skill_emoji_count += feedback_skill_emoji_count
        if feedback_skill_emoji_count < required_emoji_count:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_missing_skill_emoji",
                student_id=student_id,
                field="feedback_text",
                limit=required_emoji_count,
                reason="feedback does not preserve the frozen Skill emoji family and density",
            )
        feedback_without_name = _normalize_match_text(feedback_text).replace(
            _normalize_match_text(names_by_id[student_id]),
            "",
        )
        feedback_lexical_chars = _lexical_character_count(feedback_without_name)
        generic_remainder = unicodedata.normalize(
            "NFKC", feedback_without_name
        ).casefold()
        for phrase in _GENERIC_FEEDBACK_PHRASES:
            generic_remainder = generic_remainder.replace(phrase.casefold(), "")
        generic_remainder = "".join(
            character
            for character in generic_remainder
            if unicodedata.category(character).startswith(("L", "N"))
        )
        if not generic_remainder:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_generic",
                student_id=student_id,
                field="feedback_text",
                reason="initial feedback contains only generic encouragement",
            )
        if rich_evidence:
            paragraph_count = len(_feedback_paragraphs(feedback_text))
            if paragraph_count < 2 or paragraph_count > 4:
                raise ClassCommentaryStructuredFeedbackValidationError(
                    "student_feedback_paragraph_count_invalid",
                    student_id=student_id,
                    field="feedback_text",
                    limit=4,
                    reason="rich evidence requires 2 to 4 non-empty paragraphs",
                )
            if feedback_lexical_chars < CLASS_COMMENTARY_RICH_FEEDBACK_MIN_LEXICAL_CHARS:
                raise ClassCommentaryStructuredFeedbackValidationError(
                    "student_feedback_too_short",
                    student_id=student_id,
                    field="feedback_text",
                    limit=CLASS_COMMENTARY_RICH_FEEDBACK_MIN_LEXICAL_CHARS,
                    reason="rich evidence feedback is too short to cover the supported points",
                )
        elif feedback_lexical_chars < CLASS_COMMENTARY_SPARSE_FEEDBACK_MIN_LEXICAL_CHARS:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_too_short",
                student_id=student_id,
                field="feedback_text",
                limit=CLASS_COMMENTARY_SPARSE_FEEDBACK_MIN_LEXICAL_CHARS,
                reason="initial feedback is too short to communicate useful evidence",
            )
        if (rich_evidence or evidence_has_problem) and not _has_concrete_next_action(
            feedback_text
        ):
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_missing_next_action",
                student_id=student_id,
                field="feedback_text",
                reason="feedback needs a concrete next action supported by the evidence",
            )
    if (
        emoji_density == "occasional"
        and declares_concrete_emoji_family
        and total_skill_emoji_count == 0
    ):
        raise ClassCommentaryStructuredFeedbackValidationError(
            "batch_feedback_missing_skill_emoji",
            field="feedback_text",
            limit=1,
            reason="the class feedback drops every frozen Skill emoji despite an explicit low-density emoji family",
        )


def canonicalize_class_commentary_structured_feedback(
    *,
    structured_feedback: object,
    generation: Mapping[str, object],
    validate_generation_contract: bool = True,
    allowed_graph_evidence_refs_by_student: Mapping[int, list[str]] | None = None,
    require_batch_graph_refs: bool = False,
) -> dict:
    if validate_generation_contract:
        validate_class_commentary_structured_generation_contract(generation)
    try:
        parsed = _parse_json(structured_feedback)
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response is not valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response is not a JSON object",
        )
    if parsed.get("schema_version") != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "feedback_schema_mismatch",
            reason="response schema version does not match generation",
        )
    batch_isolated = str(generation.get("student_history_memory_mode") or "") == (
        CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
    )
    batch_response_with_refs = batch_isolated and (
        require_batch_graph_refs
        or "used_graph_evidence_refs_by_student" in parsed
    )
    try:
        envelope = (
            _BatchIsolatedStudentFeedbackEnvelopeV1.model_validate(parsed)
            if batch_response_with_refs
            else _StudentFeedbackEnvelopeV1.model_validate(parsed)
        )
    except ValidationError as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response does not match the structured feedback schema",
        ) from exc

    eligible_ids, names_by_id = _parse_frozen_scope(generation)
    eligible_id_set = set(eligible_ids)
    normalized_roster = [
        (position, student_id, _normalize_match_text(student_name))
        for position, (student_id, student_name) in enumerate(names_by_id.items())
    ]
    items_by_id: dict[int, str] = {}
    for item in envelope.items:
        student_id = int(item.student_id)
        if student_id <= 0 or student_id not in names_by_id or student_id not in eligible_id_set:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_unknown_student",
                student_id=student_id if student_id > 0 else None,
                field="student_id",
            )
        if student_id in items_by_id:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_duplicate_student",
                student_id=student_id,
                field="student_id",
            )
        normalized_text = normalize_class_commentary_feedback_text(item.feedback_text)
        if not normalized_text or _only_student_name_and_punctuation(
            normalized_text,
            names_by_id[student_id],
        ):
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_empty",
                student_id=student_id,
                field="feedback_text",
            )
        if len(normalized_text) > CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_too_long",
                student_id=student_id,
                field="feedback_text",
                limit=CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT,
            )
        normalized_match_text = _normalize_match_text(normalized_text)
        matched_student_ids = {
            matched_student_id
            for _, _, matched_student_id in _match_normalized_student_name_spans(
                normalized_match_text,
                normalized_roster,
            )
        }
        if any(matched_student_id != student_id for matched_student_id in matched_student_ids):
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_cross_student_reference",
                student_id=student_id,
                field="feedback_text",
            )
        items_by_id[student_id] = normalized_text

    used_graph_evidence_refs_by_student: dict[int, list[str]] = {}
    if batch_response_with_refs:
        for item in envelope.used_graph_evidence_refs_by_student:
            student_id = int(item.student_id)
            if (
                student_id not in eligible_id_set
                or student_id in used_graph_evidence_refs_by_student
            ):
                raise ClassCommentaryStructuredFeedbackValidationError(
                    "structured_feedback_invalid",
                    student_id=student_id if student_id > 0 else None,
                    field="used_graph_evidence_refs_by_student",
                )
            evidence_refs = [str(value) for value in item.evidence_refs]
            allowed_refs = (
                allowed_graph_evidence_refs_by_student.get(student_id)
                if allowed_graph_evidence_refs_by_student is not None
                else None
            )
            if (
                any(not value for value in evidence_refs)
                or len(set(evidence_refs)) != len(evidence_refs)
                or allowed_refs is None
                or not set(evidence_refs).issubset(set(allowed_refs))
            ):
                raise ClassCommentaryStructuredFeedbackValidationError(
                    "structured_feedback_invalid",
                    student_id=student_id,
                    field="used_graph_evidence_refs_by_student",
                )
            used_graph_evidence_refs_by_student[student_id] = evidence_refs
        if set(used_graph_evidence_refs_by_student) != eligible_id_set:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_coverage_mismatch",
                field="used_graph_evidence_refs_by_student",
            )

    if set(items_by_id) != eligible_id_set:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_coverage_mismatch"
        )
    if batch_isolated and require_batch_graph_refs:
        _validate_v4_initial_feedback_quality(
            generation=generation,
            eligible_ids=eligible_ids,
            names_by_id=names_by_id,
            items_by_id=items_by_id,
        )
    canonical_items = [
        {"student_id": student_id, "feedback_text": items_by_id[student_id]}
        for student_id in eligible_ids
    ]
    canonical_envelope = {
        "schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "items": canonical_items,
    }
    try:
        canonical_json = _canonical_json(canonical_envelope)
        canonical_hash = _content_hash(canonical_json)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response cannot be canonicalized",
        ) from exc
    response_items = [
        {
            "student_id": item["student_id"],
            "student_name": names_by_id[item["student_id"]],
            "feedback_text": item["feedback_text"],
        }
        for item in canonical_items
    ]
    derived_text = "\n\n".join(
        f"{item['student_name']}:\n{item['feedback_text']}"
        for item in response_items
    )
    if len(derived_text) > CLASS_COMMENTARY_STUDENT_FEEDBACK_TOTAL_LIMIT:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_too_long",
            field="feedback_text",
            limit=CLASS_COMMENTARY_STUDENT_FEEDBACK_TOTAL_LIMIT,
        )
    result = {
        "feedback_schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "structured_feedback_json": canonical_json,
        "structured_feedback_hash": canonical_hash,
        "derived_feedback_text": derived_text,
        "student_feedback_items": response_items,
    }
    if batch_response_with_refs:
        result["used_graph_evidence_refs_by_student"] = (
            used_graph_evidence_refs_by_student
        )
    return result


def canonicalize_class_commentary_structured_feedback_replay(
    *,
    structured_feedback: object,
    frozen_structured_feedback: object,
) -> dict:
    try:
        frozen_parsed = _parse_json(frozen_structured_feedback)
        frozen_envelope = _StudentFeedbackEnvelopeV1.model_validate(frozen_parsed)
        parsed = _parse_json(structured_feedback)
        envelope = _StudentFeedbackEnvelopeV1.model_validate(parsed)
    except (TypeError, json.JSONDecodeError, ValidationError, RecursionError) as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response does not match the frozen structured feedback schema",
        ) from exc

    frozen_student_ids: list[int] = []
    for item in frozen_envelope.items:
        student_id = int(item.student_id)
        if student_id <= 0 or student_id in frozen_student_ids:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "structured_feedback_invalid",
                reason="frozen structured feedback scope is invalid",
            )
        frozen_student_ids.append(student_id)
    if not frozen_student_ids:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="frozen structured feedback scope is empty",
        )

    frozen_student_id_set = set(frozen_student_ids)
    items_by_id: dict[int, str] = {}
    for item in envelope.items:
        student_id = int(item.student_id)
        if student_id <= 0 or student_id not in frozen_student_id_set:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_unknown_student",
                student_id=student_id if student_id > 0 else None,
                field="student_id",
            )
        if student_id in items_by_id:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_duplicate_student",
                student_id=student_id,
                field="student_id",
            )
        normalized_text = normalize_class_commentary_feedback_text(item.feedback_text)
        if not normalized_text:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_empty",
                student_id=student_id,
                field="feedback_text",
            )
        if len(normalized_text) > CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_too_long",
                student_id=student_id,
                field="feedback_text",
                limit=CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT,
            )
        items_by_id[student_id] = normalized_text

    if set(items_by_id) != frozen_student_id_set:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_coverage_mismatch"
        )
    canonical_envelope = {
        "schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "items": [
            {
                "student_id": student_id,
                "feedback_text": items_by_id[student_id],
            }
            for student_id in frozen_student_ids
        ],
    }
    canonical_json = _canonical_json(canonical_envelope)
    return {
        "feedback_schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "structured_feedback_json": canonical_json,
        "structured_feedback_hash": _content_hash(canonical_json),
    }


def _validate_v1_feedback(
    *,
    structured_json: object,
    stored_hash: str,
    derived_text: str,
    generation: Mapping[str, object],
) -> list[dict]:
    canonical = canonicalize_class_commentary_structured_feedback(
        structured_feedback=structured_json,
        generation=generation,
    )
    if (
        str(structured_json or "") != canonical["structured_feedback_json"]
        or stored_hash != canonical["structured_feedback_hash"]
    ):
        raise ValueError("structured feedback integrity check failed")
    if derived_text != canonical["derived_feedback_text"]:
        raise ValueError("structured feedback derived text is invalid")
    return canonical["student_feedback_items"]


def build_class_commentary_feedback_read_envelope(
    *,
    schema_version: object,
    structured_json: object,
    stored_hash: object,
    derived_text: object,
    generation: Mapping[str, object] | None,
    allow_empty_generation_payload: bool = False,
) -> dict:
    normalized_schema_version = str(schema_version or "")
    normalized_hash = str(stored_hash or "")
    normalized_derived_text = str(derived_text or "")
    if not normalized_schema_version:
        return {
            "feedback_schema_version": "",
            "feedback_schema_status": "plain_text",
            "student_feedback_items": [],
            "structured_feedback_hash": "",
            "derived_feedback_text": normalized_derived_text,
            "writable": True,
        }
    if normalized_schema_version != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1:
        return {
            "feedback_schema_version": normalized_schema_version,
            "feedback_schema_status": "unsupported",
            "student_feedback_items": [],
            "structured_feedback_hash": normalized_hash,
            "derived_feedback_text": normalized_derived_text,
            "writable": False,
        }
    if generation is None:
        return _invalid_envelope(
            schema_version=normalized_schema_version,
            stored_hash=normalized_hash,
            derived_text=normalized_derived_text,
        )
    if allow_empty_generation_payload and str(generation.get("status") or "") in {
        "generating",
        "failed",
    }:
        payload_is_empty = (
            str(structured_json or "") == ""
            and normalized_hash == ""
            and normalized_derived_text == ""
        )
        try:
            if not payload_is_empty:
                raise ValueError("nonterminal structured generation has result data")
            validate_class_commentary_structured_generation_contract(generation)
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
            return _invalid_envelope(
                schema_version=normalized_schema_version,
                stored_hash=normalized_hash,
                derived_text=normalized_derived_text,
            )
        return {
            "feedback_schema_version": normalized_schema_version,
            "feedback_schema_status": "supported",
            "student_feedback_items": [],
            "structured_feedback_hash": "",
            "derived_feedback_text": "",
            "writable": False,
        }
    try:
        response_items = _validate_v1_feedback(
            structured_json=structured_json,
            stored_hash=normalized_hash,
            derived_text=normalized_derived_text,
            generation=generation,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return _invalid_envelope(
            schema_version=normalized_schema_version,
            stored_hash=normalized_hash,
            derived_text=normalized_derived_text,
        )
    return {
        "feedback_schema_version": normalized_schema_version,
        "feedback_schema_status": "supported",
        "student_feedback_items": response_items,
        "structured_feedback_hash": normalized_hash,
        "derived_feedback_text": normalized_derived_text,
        "writable": True,
    }
