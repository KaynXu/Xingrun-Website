from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


MATH_SOURCE_COVERAGE_GROUPS = (
    ("勾股逆向：三角形三边满足 a²+b²=c²", ("逆向", "三角形三边", "勾股逆定理")),
    ("份数计算", ("份数", "一份", "份长度", "几份")),
    ("α+β 和角推导", ("α+β", "和角", "45°", "45度")),
    ("二倍角关系", ("2α", "2β", "4β", "二倍角")),
    ("垂直平分线构造", ("垂直平分线",)),
    ("配方法推导", ("配方法", "一元二次")),
    ("互余角关系", ("互余",)),
)


@dataclass(frozen=True)
class SourceCoverageGroup:
    label: str
    terms: tuple[str, ...]


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def compact_text(value: str) -> str:
    return re.sub(r"[\s,，。.!！?？、:：;；《》「」“”\"'`（）()\[\]【】\-_/]+", "", value)


def compact_contains_any(text: str, terms: tuple[str, ...]) -> bool:
    compact = compact_text(text)
    return any((term_compact := compact_text(term)) and term_compact in compact for term in terms)


def _source_brief_data(source_brief: Any) -> dict[str, Any]:
    if source_brief is None:
        return {}
    if hasattr(source_brief, "model_dump"):
        data = source_brief.model_dump()
        return data if isinstance(data, dict) else {}
    return source_brief if isinstance(source_brief, dict) else {}


def _coverage_terms_from_text(value: str) -> tuple[str, ...]:
    terms = []
    for part in re.split(r"[\s,，。.!！?？、:：;；《》「」“”\"'`（）()\[\]【】\-_/—与]+", value):
        text = part.strip()
        if len(text) >= 3 and text not in terms:
            terms.append(text)
    compact = compact_text(value)
    if len(compact) >= 3 and compact not in terms:
        terms.append(compact)
    return tuple(terms)


def _iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_iter_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_iter_strings(item))
        return strings
    return []


def plan_text_blob(plan: dict[str, Any]) -> str:
    return "\n".join(_iter_strings(plan))


def source_coverage_groups(source_brief: Any, *, subject_key: str) -> list[SourceCoverageGroup]:
    data = _source_brief_data(source_brief)
    if not data:
        return []
    groups: list[SourceCoverageGroup] = []

    for point in data.get("knowledge_points") or []:
        if not isinstance(point, dict):
            continue
        name = _clean_text(point.get("name"))
        if len(name) >= 3:
            groups.append(SourceCoverageGroup(name[:28], _coverage_terms_from_text(name) or (name,)))

    for chain in data.get("method_chains") or []:
        if not isinstance(chain, dict):
            continue
        name = _clean_text(chain.get("name"))
        steps = tuple(_clean_text(step) for step in (chain.get("steps") or []) if _clean_text(step))
        terms = tuple(
            term
            for source in (name, *steps[:4])
            for term in _coverage_terms_from_text(source)
            if len(term) >= 3
        )
        if terms:
            groups.append(SourceCoverageGroup((name or terms[0])[:28], terms))

    cleaned_text = _clean_text(data.get("cleaned_text"))
    if subject_key == "math" and cleaned_text:
        for label, terms in MATH_SOURCE_COVERAGE_GROUPS:
            if compact_contains_any(cleaned_text, terms):
                groups.append(SourceCoverageGroup(label, terms))

    deduped: list[SourceCoverageGroup] = []
    seen: set[str] = set()
    for group in groups:
        normalized_label = compact_text(group.label)
        if not normalized_label or normalized_label in seen:
            continue
        seen.add(normalized_label)
        deduped.append(group)
    return deduped[:10]


def missing_source_coverage_groups(
    normalized_plan: dict[str, Any],
    source_brief: Any,
    *,
    subject_key: str,
) -> list[SourceCoverageGroup]:
    groups = source_coverage_groups(source_brief, subject_key=subject_key)
    if len(groups) < 4:
        return []
    plan_text = plan_text_blob(normalized_plan)
    return [group for group in groups if not compact_contains_any(plan_text, group.terms)]


def source_coverage_trace_payload(source_brief: Any, *, subject_key: str) -> list[dict[str, Any]]:
    return [
        {"label": group.label, "terms": list(group.terms[:4])}
        for group in source_coverage_groups(source_brief, subject_key=subject_key)
    ]
