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
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])\s+|\n+")
_METHOD_SPLIT_RE = re.compile(r"\s*(?:->|→|、|，|,|；|;)\s*")


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
    return [item.strip() for item in _SENTENCE_SPLIT_RE.split(text) if item.strip()]


def _evidence_id(index: int) -> str:
    return f"ev-{index:03d}"


def _make_evidence(cleaned: str, sentence: str, index: int, *, kind: str = "text") -> SourceEvidence:
    start = cleaned.find(sentence)
    if start < 0:
        start = 0
    return SourceEvidence(
        id=_evidence_id(index),
        source="summary_text",
        quote=sentence[:180],
        offset_start=start,
        offset_end=start + len(sentence),
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


def build_deterministic_source_brief(
    *,
    raw_text: str,
    subject: str = "",
    topic: str = "",
    weak_points: str = "",
    user_requirements: str = "",
) -> ReviewPlanSourceBrief:
    cleaned = clean_source_text(raw_text)
    sentences = _sentences(cleaned)
    evidence_items = [_make_evidence(cleaned, sentence, index + 1) for index, sentence in enumerate(sentences[:18])]
    evidence_ids = [item.id for item in evidence_items[:3]]
    title_candidates = _title_candidates(cleaned, topic)

    knowledge_points: list[SourceKnowledgePoint] = []
    if weak_points.strip():
        knowledge_points.append(SourceKnowledgePoint(name=weak_points.strip(), evidence_ids=evidence_ids, confidence=0.72))
    for sentence in sentences:
        if any(token in sentence for token in ("知识点", "方法", "定理", "公式", "轨迹", "函数", "方程", "几何")):
            name = sentence.strip("。；; ")
            if name and all(item.name != name for item in knowledge_points):
                knowledge_points.append(SourceKnowledgePoint(name=name[:60], evidence_ids=evidence_ids, confidence=0.68))
        if len(knowledge_points) >= 8:
            break

    method_chains: list[SourceMethodChain] = []
    for sentence in sentences:
        if "方法" in sentence or "先" in sentence or "步骤" in sentence or "->" in sentence or "→" in sentence:
            parts = [part for part in _METHOD_SPLIT_RE.split(sentence.strip("。；; ")) if part]
            if len(parts) >= 2:
                method_chains.append(SourceMethodChain(name=parts[0][:40], steps=parts[:6], evidence_ids=evidence_ids))
        if len(method_chains) >= 5:
            break

    mistakes: list[SourceMistake] = []
    for sentence in sentences:
        if any(token in sentence for token in ("易错", "错", "误看", "漏", "混淆", "卡")):
            mistakes.append(SourceMistake(name=sentence.strip("。；; ")[:80], evidence_ids=evidence_ids))
        if len(mistakes) >= 5:
            break

    examples: list[SourceExampleStem] = []
    for sentence in sentences:
        if any(token in sentence for token in ("例题", "题", "已知", "求", "证明", "动点")):
            examples.append(SourceExampleStem(stem=sentence.strip("。；; ")[:120], evidence_ids=evidence_ids))
        if len(examples) >= 6:
            break

    emphasis: list[SourceTeacherEmphasis] = []
    for sentence in sentences:
        if any(token in sentence for token in ("老师强调", "强调", "记住", "一定", "先")):
            emphasis.append(SourceTeacherEmphasis(quote=sentence.strip("。；; ")[:100], evidence_ids=evidence_ids))
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
