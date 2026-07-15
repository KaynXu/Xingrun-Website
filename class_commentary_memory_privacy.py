from __future__ import annotations

import re
from typing import Iterable


_PRIVATE_INFORMATION_PATTERNS = (
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[ -]?){14}\d(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[ -]?){17}[\dXx](?![\dXx])"),
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
    re.compile(
        r"微信号|微信ID|wechat|手机号|手机号码|联系电话|联系方式|家庭住址|住址|地址",
        re.IGNORECASE,
    ),
    re.compile(r"(?:路|街|巷|小区|社区|栋|单元)\s*\d+(?:号|室)?"),
)


def contains_class_commentary_private_information(value: object) -> bool:
    text = str(value or "")
    return any(pattern.search(text) for pattern in _PRIVATE_INFORMATION_PATTERNS)


def normalize_class_commentary_roster_name(value: object) -> str:
    return "".join(str(value or "").strip().casefold().split())


def contains_class_commentary_roster_name(
    values: Iterable[object],
    roster_names: Iterable[str],
) -> bool:
    normalized_values = [normalize_class_commentary_roster_name(value) for value in values]
    for name in roster_names:
        normalized_name = normalize_class_commentary_roster_name(name)
        if normalized_name and any(normalized_name in value for value in normalized_values):
            return True
    return False


def validate_class_commentary_memory_privacy(
    *,
    memory_text: object,
    support: Iterable[object],
    roster_names: Iterable[str],
) -> None:
    values = [memory_text, *support]
    if any(contains_class_commentary_private_information(value) for value in values):
        raise ValueError("class commentary memory contains private information")
    if contains_class_commentary_roster_name(values, roster_names):
        raise ValueError("class commentary memory contains a roster name")
