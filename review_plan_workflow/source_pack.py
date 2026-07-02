from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from review_plan_workflow.schemas import (
    LessonSourcePack,
    ReviewPlanSourceBrief,
    SourceMathBlock,
    SourceSegment,
    SourceTeacherAction,
)
from review_plan_workflow.source_brief import build_deterministic_source_brief, clean_source_text, source_text_hash


SOURCE_PACK_SCHEMA_VERSION = "lesson_source_pack_v1"
_MATH_TOKEN_RE = re.compile(
    r"(\$[^$]{1,120}\$|\\(?:sqrt|frac|angle|triangle|cong|circ)\b[^\s，。；;、]{0,40}|√\d+|[αβ]\+?[αβ]?|[a-zA-Z]\^\d|[0-9]+:[0-9√:]+)"
)
_TEACHER_ACTION_RE = re.compile(r"(必须|一定要|不能|要求|课后作业|明天抽查|背熟|重新演算|完整抄写|打五星)")


def _stable_source_id(source_type: str, source_hash: str) -> str:
    suffix = str(source_hash or "").replace("sha256:", "")[:16]
    return f"{source_type or 'text'}:{suffix}" if suffix else str(source_type or "text")


def _pack_title(brief: ReviewPlanSourceBrief, fallback: str) -> str:
    for title in brief.lesson_title_candidates:
        if str(title or "").strip():
            return str(title).strip()[:80]
    return str(fallback or "").strip()[:80]


def _dedupe_strings(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text[:80])
        if len(result) >= limit:
            break
    return result


def _build_segments(cleaned: str) -> list[SourceSegment]:
    segments: list[SourceSegment] = []
    cursor = 0
    for index, line in enumerate([line.strip() for line in str(cleaned or "").splitlines() if line.strip()], start=1):
        start = cleaned.find(line, cursor)
        if start < 0:
            start = cursor
        end = start + len(line)
        cursor = end
        kind = "heading" if index == 1 and len(line) <= 80 and not re.search(r"[。！？!?；;]", line) else "text"
        segments.append(SourceSegment(id=f"seg-{index:03d}", text=line, offset_start=start, offset_end=end, kind=kind))
        if len(segments) >= 120:
            break
    return segments


def _segment_for_offset(segments: list[SourceSegment], offset: int) -> str:
    for segment in segments:
        if segment.offset_start <= offset <= segment.offset_end:
            return segment.id
    return segments[0].id if segments else ""


def _extract_math_blocks(cleaned: str, segments: list[SourceSegment]) -> list[SourceMathBlock]:
    blocks: list[SourceMathBlock] = []
    seen: set[str] = set()
    for match in _MATH_TOKEN_RE.finditer(str(cleaned or "")):
        raw = match.group(1).strip()
        if raw in seen:
            continue
        seen.add(raw)
        latex = raw.strip("$")
        blocks.append(
            SourceMathBlock(
                id=f"math-{len(blocks) + 1:03d}",
                raw=raw,
                latex=latex,
                display=False,
                segment_id=_segment_for_offset(segments, match.start()),
            )
        )
        if len(blocks) >= 40:
            break
    return blocks


def _extract_teacher_actions(cleaned: str, segments: list[SourceSegment]) -> list[SourceTeacherAction]:
    actions: list[SourceTeacherAction] = []
    for segment in segments:
        if not _TEACHER_ACTION_RE.search(segment.text):
            continue
        action_type = "homework" if "课后作业" in segment.text else "check" if "抽查" in segment.text else "instruction"
        actions.append(
            SourceTeacherAction(
                id=f"act-{len(actions) + 1:03d}",
                text=segment.text[:160],
                action_type=action_type,
                segment_id=segment.id,
            )
        )
        if len(actions) >= 20:
            break
    return actions


def source_pack_trace_payload(source_pack: LessonSourcePack | dict | None) -> dict[str, Any]:
    if source_pack is None:
        return {}
    if hasattr(source_pack, "model_dump"):
        data = source_pack.model_dump()
    elif isinstance(source_pack, dict):
        data = source_pack
    else:
        return {}
    return {
        "schema_version": str(data.get("schema_version") or SOURCE_PACK_SCHEMA_VERSION),
        "source_id": str(data.get("source_id") or ""),
        "source_type": str(data.get("source_type") or ""),
        "title": str(data.get("title") or "")[:80],
        "language": str(data.get("language") or ""),
        "segments_count": len(data.get("segments") or []),
        "detected_topics_count": len(data.get("detected_topics") or []),
        "math_blocks_count": len(data.get("math_blocks") or []),
        "teacher_actions_count": len(data.get("teacher_actions") or []),
        "warnings": list(data.get("warnings") or [])[:10],
        "source_hash": str(data.get("source_hash") or ""),
    }


def build_lesson_source_pack(
    *,
    raw_text: str,
    source_type: str = "text",
    title: str = "",
    language: str = "zh-CN",
    subject: str = "",
    topic: str = "",
    weak_points: str = "",
    user_requirements: str = "",
    created_at: str = "",
) -> LessonSourcePack:
    brief = build_deterministic_source_brief(
        raw_text=raw_text,
        subject=subject,
        topic=topic,
        weak_points=weak_points,
        user_requirements=user_requirements,
    )
    cleaned = clean_source_text(raw_text)
    source_hash = source_text_hash(raw_text)
    segments = _build_segments(cleaned)
    topics = _dedupe_strings(
        [*brief.lesson_title_candidates, *(point.name for point in brief.knowledge_points)],
        20,
    )
    warnings = [f"missing:{field}" for field in brief.missing_fields]
    if not segments:
        warnings.append("empty_source")
    return LessonSourcePack(
        schema_version=SOURCE_PACK_SCHEMA_VERSION,
        source_id=_stable_source_id(source_type, source_hash),
        source_type=str(source_type or "text"),
        title=_pack_title(brief, title or topic),
        language=language or "zh-CN",
        segments=segments,
        detected_topics=topics,
        math_blocks=_extract_math_blocks(cleaned, segments),
        teacher_actions=_extract_teacher_actions(cleaned, segments),
        warnings=warnings,
        source_hash=source_hash,
        created_at=created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def build_lesson_source_pack_from_artifact(
    *,
    source_text: str,
    cleaned_source_text: str,
    source_text_hash_value: str,
    source_brief: object,
    source_type: str = "text",
) -> LessonSourcePack:
    if isinstance(source_brief, ReviewPlanSourceBrief):
        brief_data = source_brief.model_dump()
    elif isinstance(source_brief, dict):
        brief_data = source_brief
    else:
        brief_data = {}
    raw_text = str(source_text or cleaned_source_text or "")
    cleaned = clean_source_text(cleaned_source_text or source_text)
    source_hash = str(source_text_hash_value or brief_data.get("source_text_hash") or source_text_hash(raw_text))
    segments = _build_segments(cleaned)
    topics = _dedupe_strings(
        [
            *(brief_data.get("lesson_title_candidates") or []),
            *(str(item.get("name") or "") for item in (brief_data.get("knowledge_points") or []) if isinstance(item, dict)),
        ],
        20,
    )
    warnings = [f"missing:{field}" for field in (brief_data.get("missing_fields") or [])]
    if not segments:
        warnings.append("empty_source")
    return LessonSourcePack(
        schema_version=SOURCE_PACK_SCHEMA_VERSION,
        source_id=_stable_source_id(source_type, source_hash),
        source_type=str(source_type or "text"),
        title=_pack_title(ReviewPlanSourceBrief.model_validate(brief_data or {}), ""),
        language="zh-CN",
        segments=segments,
        detected_topics=topics,
        math_blocks=_extract_math_blocks(cleaned, segments),
        teacher_actions=_extract_teacher_actions(cleaned, segments),
        warnings=warnings,
        source_hash=source_hash,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
