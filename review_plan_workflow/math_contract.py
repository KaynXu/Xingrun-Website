from __future__ import annotations

import copy
import re
from typing import Any


LATEX_SEGMENT_PATTERN = re.compile(
    r"(?<!\\)\$\$(.+?)(?<!\\)\$\$"
    r"|(?<!\\)\$(?!\$)(.+?)(?<!\\)\$(?!\$)"
    r"|\\{1,2}\((.+?)\\{1,2}\)"
    r"|\\{1,2}\[(.+?)\\{1,2}\]",
    re.DOTALL,
)
GREEK_NAMES = {
    "alpha": r"\alpha",
    "beta": r"\beta",
}
BARE_TRIG_FRACTION_PATTERN = re.compile(
    r"(?<![A-Za-z\\])(?P<func>sin|cos|tan)\s*(?P<name>alpha|beta)\s*=\s*"
    r"\((?P<num>[0-9]+)\)\s*/\s*\((?P<den>[0-9]+)\)(?![A-Za-z])",
    re.IGNORECASE,
)
BARE_TRIG_ALPHA_BETA_SUM_PATTERN = re.compile(
    r"(?<![A-Za-z\\])(?P<func>sin|cos|tan)\s*[(（]\s*alpha\s*\+\s*beta\s*[)）]\s*=\s*"
    r"(?P<rhs>[0-9]+(?:\.[0-9]+)?)(?![A-Za-z])",
    re.IGNORECASE,
)
BARE_ALPHA_BETA_SUM_PATTERN = re.compile(
    r"(?<![A-Za-z\\])alpha\s*\+\s*beta\s*=\s*(?P<deg>[0-9]+)\s*(?:°|度|\\?circ)?(?![A-Za-z])",
    re.IGNORECASE,
)
BARE_ALPHA_BETA_PAIR_PATTERN = re.compile(
    r"(?<![A-Za-z\\])alpha\s*(?P<join>和|与|、|,|，|and)\s*beta(?![A-Za-z])",
    re.IGNORECASE,
)
BARE_ALPHA_BETA_PATTERN = re.compile(r"(?<![A-Za-z\\])alpha\s*\+\s*beta(?![A-Za-z])", re.IGNORECASE)
BARE_GREEK_CJK_PATTERN = re.compile(r"(?<![A-Za-z\\])(?P<name>alpha|beta)(?=[\u4e00-\u9fff])", re.IGNORECASE)
BARE_NUMBERED_GREEK_PATTERN = re.compile(r"(?<![A-Za-z\\])(?P<num>[0-9]+)\s*(?P<name>alpha|beta)(?![A-Za-z])", re.IGNORECASE)
BARE_GREEK_PATTERN = re.compile(r"(?<![A-Za-z\\])(?P<name>alpha|beta)(?![A-Za-z])", re.IGNORECASE)
BARE_MATH_CONTRACT_PATTERNS = (
    BARE_TRIG_FRACTION_PATTERN,
    BARE_TRIG_ALPHA_BETA_SUM_PATTERN,
    BARE_ALPHA_BETA_SUM_PATTERN,
    BARE_ALPHA_BETA_PAIR_PATTERN,
    BARE_ALPHA_BETA_PATTERN,
    BARE_GREEK_CJK_PATTERN,
    BARE_NUMBERED_GREEK_PATTERN,
    BARE_GREEK_PATTERN,
)


def _replace_bare_math_segment(text: str) -> str:
    def replace_trig(match: re.Match[str]) -> str:
        func = match.group("func").lower()
        name = GREEK_NAMES[match.group("name").lower()]
        return f"$\\{func}{name}=\\frac{{{match.group('num')}}}{{{match.group('den')}}}$"

    def replace_sum(match: re.Match[str]) -> str:
        return f"$\\alpha+\\beta={match.group('deg')}^\\circ$"

    def replace_trig_sum(match: re.Match[str]) -> str:
        func = match.group("func").lower()
        return f"$\\{func}(\\alpha+\\beta)={match.group('rhs')}$"

    def replace_pair(match: re.Match[str]) -> str:
        return f"$\\alpha${match.group('join')}$\\beta$"

    def replace_greek_cjk(match: re.Match[str]) -> str:
        return f"${GREEK_NAMES[match.group('name').lower()]}$"

    def replace_numbered_greek(match: re.Match[str]) -> str:
        return f"${match.group('num')}{GREEK_NAMES[match.group('name').lower()]}$"

    def replace_greek(match: re.Match[str]) -> str:
        return f"${GREEK_NAMES[match.group('name').lower()]}$"

    normalized = BARE_TRIG_FRACTION_PATTERN.sub(replace_trig, text)
    normalized = BARE_TRIG_ALPHA_BETA_SUM_PATTERN.sub(replace_trig_sum, normalized)
    normalized = BARE_ALPHA_BETA_SUM_PATTERN.sub(replace_sum, normalized)
    normalized = BARE_ALPHA_BETA_PAIR_PATTERN.sub(replace_pair, normalized)
    normalized = BARE_ALPHA_BETA_PATTERN.sub(r"$\\alpha+\\beta$", normalized)
    normalized = BARE_NUMBERED_GREEK_PATTERN.sub(replace_numbered_greek, normalized)
    normalized = BARE_GREEK_CJK_PATTERN.sub(replace_greek_cjk, normalized)
    return BARE_GREEK_PATTERN.sub(replace_greek, normalized)


def normalize_bare_math_text(value: str) -> str:
    pieces: list[str] = []
    position = 0
    for match in LATEX_SEGMENT_PATTERN.finditer(value):
        if match.start() > position:
            pieces.append(_replace_bare_math_segment(value[position:match.start()]))
        pieces.append(value[match.start() : match.end()])
        position = match.end()
    if position < len(value):
        pieces.append(_replace_bare_math_segment(value[position:]))
    return "".join(pieces)


def normalize_plan_math_contract(plan: dict[str, Any]) -> dict[str, Any]:
    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return normalize_bare_math_text(value)
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    return walk(copy.deepcopy(plan))


def bare_math_contract_violations(value: Any) -> list[str]:
    violations: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, str):
            stripped = LATEX_SEGMENT_PATTERN.sub("", item)
            if any(pattern.search(stripped) for pattern in BARE_MATH_CONTRACT_PATTERNS):
                violations.append(item)
        elif isinstance(item, dict):
            for nested in item.values():
                walk(nested)
        elif isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(value)
    return violations
