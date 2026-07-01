from __future__ import annotations

import hashlib
import re

from review_plan_workflow.schemas import (
    ReviewPlanSourceBrief,
    SourceEvidence,
    SourceExampleStem,
    SourceKnowledgePoint,
    SourceMethodChain,
    SourceMistake,
    SourceTeacherEmphasis,
)


SOURCE_BRIEF_SCHEMA_VERSION = "2026-07-01"
_NOISE_PATTERNS = (
    "嗯嗯",
    "呃呃",
    "然后然后",
    "好吧好吧",
    "对吧对吧",
)
_TITLE_MARKERS = ("本节课主题：", "主题：", "topic:")
_SENTENCE_SCAN_RE = re.compile(r"[^。\n！？!?；;]+[。！？!?；;]?")
_METHOD_SPLIT_RE = re.compile(r"\s*(?:->|→|、|，|,|；|;)\s*")
_KNOWLEDGE_MARKERS = ("知识点：", "知识点:", "重点：", "重点:", "结论：", "结论:", "定理：", "定理:", "公式：", "公式:", "性质：", "性质:")
_EXAMPLE_MARKERS = ("例题：", "例题:", "题目：", "题目:", "已知", "求证", "求解", "证明")
_MISTAKE_MARKERS = ("易错：", "易错:", "常错：", "常错:", "常见错误", "错误：", "错误:", "误区：", "误区:", "误看", "看漏", "混淆", "漏看", "把")
_EMPHASIS_MARKERS = ("老师强调：", "老师强调:", "强调：", "强调:", "一定要", "要注意", "重点是", "记住", "特别注意")
_METHOD_MARKERS = ("方法：", "方法:", "步骤：", "步骤:", "思路：", "思路:", "先", "然后", "最后")


def source_text_hash(text: str) -> str:
    digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def clean_source_text(text: str) -> str:
    cleaned = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    for pattern in _NOISE_PATTERNS:
        cleaned = cleaned.replace(pattern, "")
    lines = [" ".join(line.split()) for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _sentences(text: str) -> list[str]:
    return [sentence for sentence, _, _ in _scan_sentence_records(text)]


def _evidence_id(index: int) -> str:
    return f"ev-{index:03d}"


def _scan_sentence_records(text: str) -> list[tuple[str, int, int]]:
    records: list[tuple[str, int, int]] = []
    for match in _SENTENCE_SCAN_RE.finditer(text):
        raw = match.group()
        if not raw.strip():
            continue
        start = match.start()
        trimmed_start = start + (len(raw) - len(raw.lstrip()))
        trimmed_end = start + len(raw.rstrip())
        sentence = text[trimmed_start:trimmed_end].strip()
        if sentence:
            records.append((sentence, trimmed_start, trimmed_end))
    return records


def _make_evidence(sentence: str, start: int, end: int, index: int, *, kind: str = "text") -> SourceEvidence:
    return SourceEvidence(
        id=_evidence_id(index),
        source="summary_text",
        quote=sentence[:180],
        offset_start=start,
        offset_end=end,
        kind=kind,
    )


def _title_candidates(cleaned: str, explicit_topic: str) -> list[str]:
    titles: list[str] = []
    if explicit_topic.strip():
        titles.append(explicit_topic.strip())
    for marker in _TITLE_MARKERS:
        if marker in cleaned:
            candidate = cleaned.split(marker, 1)[1].splitlines()[0].strip(" ：:。；;")
            if candidate and candidate not in titles:
                titles.append(candidate)
            break
    return titles[:3]


def _sentence_has_marker(sentence: str, markers: tuple[str, ...]) -> bool:
    return any(marker in sentence for marker in markers)


def _strip_marker_payload(sentence: str, markers: tuple[str, ...]) -> str:
    for marker in markers:
        if marker in sentence:
            return sentence.split(marker, 1)[1].strip(" ：:。；;")
    return sentence.strip("。；; ")


def _looks_like_method_chain(sentence: str) -> bool:
    if _sentence_has_marker(sentence, ("方法：", "方法:", "步骤：", "步骤:", "思路：", "思路:")):
        return True
    if "->" in sentence or "→" in sentence:
        return True
    if _sentence_has_marker(sentence, ("先",)) and any(marker in sentence for marker in ("再", "然后", "最后", "接着")) and any(
        marker in sentence for marker in ("方法", "步骤", "思路", "过程", "顺序")
    ):
        return True
    return False


def _looks_like_knowledge_point(sentence: str) -> bool:
    if _sentence_has_marker(sentence, _KNOWLEDGE_MARKERS):
        return True
    return False


def _looks_like_example(sentence: str) -> bool:
    if _sentence_has_marker(sentence, _EXAMPLE_MARKERS):
        return True
    if sentence.startswith("求") and not sentence.startswith("先求"):
        return True
    if sentence.endswith(("？", "?")) and any(token in sentence for token in ("轨迹", "动点", "函数", "方程", "几何", "点", "求")):
        return True
    return False


def _looks_like_mistake(sentence: str) -> bool:
    if _sentence_has_marker(sentence, ("易错：", "易错:", "常错：", "常错:", "常见错误", "错误：", "错误:", "误区：", "误区:")):
        return True
    if "误看" in sentence or "看漏" in sentence or "混淆" in sentence or "漏看" in sentence:
        return True
    if "把" in sentence and "看成" in sentence:
        return True
    return False


def _looks_like_emphasis(sentence: str) -> bool:
    if _sentence_has_marker(sentence, _EMPHASIS_MARKERS):
        return True
    return False


def build_deterministic_source_brief(
    *,
    raw_text: str,
    subject: str = "",
    topic: str = "",
    weak_points: str = "",
    user_requirements: str = "",
) -> ReviewPlanSourceBrief:
    cleaned = clean_source_text(raw_text)
    sentence_records = _scan_sentence_records(cleaned)
    evidence_items = [
        _make_evidence(sentence, start, end, index + 1)
        for index, (sentence, start, end) in enumerate(sentence_records[:18])
    ]
    sentence_records_with_evidence = [
        (sentence, start, end, evidence.id)
        for (sentence, start, end), evidence in zip(sentence_records[:18], evidence_items)
    ]
    title_candidates = _title_candidates(cleaned, topic)

    knowledge_points: list[SourceKnowledgePoint] = []
    if weak_points.strip():
        knowledge_points.append(SourceKnowledgePoint(name=weak_points.strip(), evidence_ids=[], confidence=0.72))
    for sentence, _, _, evidence_id in sentence_records_with_evidence:
        if not _looks_like_knowledge_point(sentence):
            continue
        name = _strip_marker_payload(sentence, _KNOWLEDGE_MARKERS)
        if not name:
            continue
        existing = next((item for item in knowledge_points if item.name == name[:60]), None)
        if existing is None:
            knowledge_points.append(SourceKnowledgePoint(name=name[:60], evidence_ids=[evidence_id], confidence=0.68))
        else:
            if evidence_id not in existing.evidence_ids:
                existing.evidence_ids.append(evidence_id)
            existing.confidence = max(existing.confidence, 0.68)
        if len(knowledge_points) >= 8:
            break

    method_chains: list[SourceMethodChain] = []
    for sentence, _, _, evidence_id in sentence_records_with_evidence:
        if not _looks_like_method_chain(sentence):
            continue
        parts = [part for part in _METHOD_SPLIT_RE.split(sentence.strip("。；; ")) if part]
        if len(parts) < 2:
            continue
        method_chains.append(
            SourceMethodChain(
                name=parts[0][:40],
                steps=parts[:6],
                evidence_ids=[evidence_id],
            )
        )
        if len(method_chains) >= 5:
            break

    mistakes: list[SourceMistake] = []
    for sentence, _, _, evidence_id in sentence_records_with_evidence:
        if not _looks_like_mistake(sentence):
            continue
        mistakes.append(SourceMistake(name=sentence.strip("。；; ")[:80], evidence_ids=[evidence_id]))
        if len(mistakes) >= 5:
            break

    examples: list[SourceExampleStem] = []
    for sentence, _, _, evidence_id in sentence_records_with_evidence:
        if not _looks_like_example(sentence):
            continue
        examples.append(SourceExampleStem(stem=sentence.strip("。；; ")[:120], evidence_ids=[evidence_id]))
        if len(examples) >= 6:
            break

    emphasis: list[SourceTeacherEmphasis] = []
    for sentence, _, _, evidence_id in sentence_records_with_evidence:
        if not _looks_like_emphasis(sentence):
            continue
        emphasis.append(SourceTeacherEmphasis(quote=sentence.strip("。；; ")[:100], evidence_ids=[evidence_id]))
        if len(emphasis) >= 5:
            break

    missing_fields = []
    if not title_candidates:
        missing_fields.append("topic")
    if not knowledge_points:
        missing_fields.append("knowledge_points")
    if not examples:
        missing_fields.append("example_stems")

    signal_count = len(title_candidates) + len(knowledge_points) + len(method_chains) + len(mistakes) + len(examples) + len(emphasis)
    confidence = min(0.9, 0.35 + signal_count * 0.08)
    if missing_fields:
        confidence = min(confidence, 0.65)

    return ReviewPlanSourceBrief(
        schema_version=SOURCE_BRIEF_SCHEMA_VERSION,
        source_text_hash=source_text_hash(raw_text),
        cleaned_text=cleaned,
        lesson_title_candidates=title_candidates,
        knowledge_points=knowledge_points,
        method_chains=method_chains,
        common_mistakes=mistakes,
        example_stems=examples,
        teacher_emphasis=emphasis,
        excluded_noise=[pattern for pattern in _NOISE_PATTERNS if pattern in str(raw_text or "")],
        missing_fields=missing_fields,
        evidence_map=evidence_items,
        confidence=round(confidence, 2),
    )
