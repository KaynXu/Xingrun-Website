from __future__ import annotations

import re
import hashlib
import json
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
SOURCE_PACK_PARSER_VERSION = "source_pack_parser_v2"
MAX_SOURCE_SEGMENTS = 240
SEGMENT_MAX_CHARS = 900
_MATH_TOKEN_RE = re.compile(
    r"(\$[^$]{1,120}\$|\\(?:sqrt|frac|angle|triangle|cong|circ)\b[^\s，。；;、]{0,40}|√\d+|[αβ]\+?[αβ]?|[a-zA-Z]\^\d|[0-9]+:[0-9√:]+)"
)
_TEACHER_ACTION_RE = re.compile(r"(必须|一定要|不能|要求|课后作业|明天抽查|背熟|重新演算|完整抄写|打五星)")
_SECTION_HEADING_RE = re.compile(
    r"^\s*(?:第[一二三四五六七八九十0-9]+部分|[一二三四五六七八九十0-9]+[、.．]|课堂收尾)\s*[:：]?\s*(.{0,90})\s*$"
)
_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
_LOCAL_TOPIC_MARKERS = ("主题：", "主题:", "知识点：", "知识点:", "重点：", "重点:", "结论：", "结论:", "定理：", "定理:", "公式：", "公式:")
_EXAMPLE_MARKERS = ("例题：", "例题:", "题目：", "题目:", "已知", "求证", "求解", "证明")


def source_pack_cache_key(
    *,
    raw_source_hash: str,
    cleaned_source_hash: str,
    schema_version: str = SOURCE_PACK_SCHEMA_VERSION,
    parser_version: str = SOURCE_PACK_PARSER_VERSION,
) -> str:
    payload = {
        "raw_source_hash": str(raw_source_hash or ""),
        "cleaned_source_hash": str(cleaned_source_hash or ""),
        "schema_version": str(schema_version or SOURCE_PACK_SCHEMA_VERSION),
        "parser_version": str(parser_version or SOURCE_PACK_PARSER_VERSION),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def source_pack_cache_key_for_text(*, raw_text: str, cleaned_text: str = "") -> str:
    raw_hash = source_text_hash(raw_text)
    cleaned_hash = source_text_hash(cleaned_text if cleaned_text else clean_source_text(raw_text))
    return source_pack_cache_key(raw_source_hash=raw_hash, cleaned_source_hash=cleaned_hash)


def source_pack_needs_rebuild(
    source_pack: LessonSourcePack | dict | None,
    *,
    raw_source_hash: str,
    cleaned_source_hash: str,
) -> bool:
    if source_pack is None:
        return True
    if hasattr(source_pack, "model_dump"):
        data = source_pack.model_dump()
    elif isinstance(source_pack, dict):
        data = source_pack
    else:
        return True
    expected_key = source_pack_cache_key(
        raw_source_hash=raw_source_hash,
        cleaned_source_hash=cleaned_source_hash,
    )
    return not (
        str(data.get("schema_version") or "") == SOURCE_PACK_SCHEMA_VERSION
        and str(data.get("parser_version") or "") == SOURCE_PACK_PARSER_VERSION
        and str(data.get("raw_source_hash") or data.get("source_hash") or "") == str(raw_source_hash or "")
        and str(data.get("cleaned_source_hash") or "") == str(cleaned_source_hash or "")
        and str(data.get("cache_key") or "") == expected_key
    )


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


def _segment_cache_key(*, chunk_hash: str, section_title: str = "") -> str:
    payload = {
        "chunk_hash": str(chunk_hash or ""),
        "section_title": str(section_title or "")[:120],
        "schema_version": SOURCE_PACK_SCHEMA_VERSION,
        "parser_version": SOURCE_PACK_PARSER_VERSION,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _heading_title(line: str, *, line_index: int) -> str:
    text = str(line or "").strip()
    if not text:
        return ""
    match = _SECTION_HEADING_RE.match(text)
    if match:
        return text[:90]
    if line_index == 1 and len(text) <= 90 and not re.search(r"[。！？!?；;]", text):
        return text[:90]
    return ""


def _split_long_line(line: str) -> list[str]:
    text = str(line or "").strip()
    if not text:
        return []
    if len(text) <= SEGMENT_MAX_CHARS:
        return [text]
    parts = [part.strip() for part in _SENTENCE_RE.findall(text) if part.strip()]
    if not parts:
        parts = [text[index : index + SEGMENT_MAX_CHARS] for index in range(0, len(text), SEGMENT_MAX_CHARS)]
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(part) > SEGMENT_MAX_CHARS:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(part[index : index + SEGMENT_MAX_CHARS] for index in range(0, len(part), SEGMENT_MAX_CHARS))
            continue
        if current and len(current) + len(part) > SEGMENT_MAX_CHARS:
            chunks.append(current)
            current = part
        else:
            current = f"{current}{part}" if current else part
    if current:
        chunks.append(current)
    return chunks


def _local_topics(text: str, section_title: str) -> list[str]:
    topics = [section_title] if section_title else []
    for marker in _LOCAL_TOPIC_MARKERS:
        if marker not in text:
            continue
        tail = text.split(marker, 1)[1].strip()
        if tail:
            topics.append(re.split(r"[。！？!?；;\n]", tail, 1)[0][:60])
    return _dedupe_strings(topics, 6)


def _build_segments(cleaned: str) -> list[SourceSegment]:
    segments: list[SourceSegment] = []
    cursor = 0
    section_index = 0
    current_section_id = ""
    current_section_title = ""
    current_chunk_index = 0
    for line_index, line in enumerate([line.strip() for line in str(cleaned or "").splitlines() if line.strip()], start=1):
        start = cleaned.find(line, cursor)
        if start < 0:
            start = cursor
        end = start + len(line)
        cursor = end
        heading = _heading_title(line, line_index=line_index)
        if heading:
            section_index += 1
            current_section_id = f"sec-{section_index:03d}"
            current_section_title = heading
            current_chunk_index = 0
        elif not current_section_id:
            section_index = 1
            current_section_id = "sec-001"
            current_section_title = ""
        chunks = _split_long_line(line)
        chunk_cursor = start
        for chunk in chunks:
            chunk_start = cleaned.find(chunk, chunk_cursor)
            if chunk_start < 0:
                chunk_start = chunk_cursor
            chunk_end = chunk_start + len(chunk)
            chunk_cursor = chunk_end
            current_chunk_index += 1
            chunk_hash = source_text_hash(chunk)
            kind = "heading" if heading and chunk == chunks[0] else "text"
            segments.append(
                SourceSegment(
                    id=f"seg-{len(segments) + 1:03d}",
                    text=chunk,
                    offset_start=chunk_start,
                    offset_end=chunk_end,
                    kind=kind,
                    section_id=current_section_id,
                    section_title=current_section_title,
                    chunk_index=current_chunk_index,
                    chunk_hash=chunk_hash,
                    extraction_cache_key=_segment_cache_key(chunk_hash=chunk_hash, section_title=current_section_title),
                    local_topics=_local_topics(chunk, current_section_title),
                    example_count=sum(1 for marker in _EXAMPLE_MARKERS if marker in chunk),
                    math_count=len(_MATH_TOKEN_RE.findall(chunk)),
                    char_count=len(chunk),
                )
            )
            if len(segments) >= MAX_SOURCE_SEGMENTS:
                return segments
        if len(segments) >= MAX_SOURCE_SEGMENTS:
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
    segments = data.get("segments") or []
    section_ids = {
        str(segment.get("section_id") or "")
        for segment in segments
        if isinstance(segment, dict) and str(segment.get("section_id") or "")
    }
    segment_cache_key_count = len(
        [
            segment
            for segment in segments
            if isinstance(segment, dict) and str(segment.get("extraction_cache_key") or "")
        ]
    )
    return {
        "schema_version": str(data.get("schema_version") or SOURCE_PACK_SCHEMA_VERSION),
        "parser_version": str(data.get("parser_version") or ""),
        "source_id": str(data.get("source_id") or ""),
        "source_type": str(data.get("source_type") or ""),
        "title": str(data.get("title") or "")[:80],
        "language": str(data.get("language") or ""),
        "segments_count": len(segments),
        "sections_count": len(section_ids),
        "segment_cache_key_count": segment_cache_key_count,
        "detected_topics_count": len(data.get("detected_topics") or []),
        "math_blocks_count": len(data.get("math_blocks") or []),
        "teacher_actions_count": len(data.get("teacher_actions") or []),
        "warnings": list(data.get("warnings") or [])[:10],
        "source_hash": str(data.get("source_hash") or ""),
        "raw_source_hash": str(data.get("raw_source_hash") or ""),
        "cleaned_source_hash": str(data.get("cleaned_source_hash") or ""),
        "cache_key": str(data.get("cache_key") or ""),
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
    cleaned_hash = source_text_hash(cleaned)
    segments = _build_segments(cleaned)
    topics = _dedupe_strings(
        [*brief.lesson_title_candidates, *(point.name for point in brief.knowledge_points)],
        20,
    )
    warnings = [f"missing:{field}" for field in brief.missing_fields]
    if not segments:
        warnings.append("empty_source")
    if len(cleaned) > SEGMENT_MAX_CHARS or len(segments) > 20:
        warnings.append("long_source_segmented")
    return LessonSourcePack(
        schema_version=SOURCE_PACK_SCHEMA_VERSION,
        parser_version=SOURCE_PACK_PARSER_VERSION,
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
        raw_source_hash=source_hash,
        cleaned_source_hash=cleaned_hash,
        cache_key=source_pack_cache_key(raw_source_hash=source_hash, cleaned_source_hash=cleaned_hash),
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
    cleaned_hash = source_text_hash(cleaned)
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
    if len(cleaned) > SEGMENT_MAX_CHARS or len(segments) > 20:
        warnings.append("long_source_segmented")
    return LessonSourcePack(
        schema_version=SOURCE_PACK_SCHEMA_VERSION,
        parser_version=SOURCE_PACK_PARSER_VERSION,
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
        raw_source_hash=source_hash,
        cleaned_source_hash=cleaned_hash,
        cache_key=source_pack_cache_key(raw_source_hash=source_hash, cleaned_source_hash=cleaned_hash),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
