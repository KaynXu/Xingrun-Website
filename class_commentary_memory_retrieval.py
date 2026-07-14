from __future__ import annotations

import json
from typing import Callable, Iterable, Mapping, Optional

from class_commentary_memory import ClassCommentaryMemoryService


CLASS_COMMENTARY_MEMORY_MIN_CONFIDENCE = 0.7


def empty_class_commentary_memory_context(reason: str = "") -> dict:
    return {
        "records": [],
        "rendered_text": "",
        "student_history_memories": [],
        "teacher_style_memories": [],
        "retrieval_status": "degraded" if reason else "empty",
        "degraded_reason": str(reason or ""),
    }


def _json_list(value: object) -> list:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _positive_int(value: object) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 0
    return normalized if normalized > 0 else 0


def _record_map(records: Iterable[Mapping[str, object]]) -> dict[int, dict]:
    mapped = {}
    for record in records:
        record_id = _positive_int(record.get("id"))
        if record_id:
            mapped[record_id] = dict(record)
    return mapped


def _candidate_record_id(candidate: Mapping[str, object]) -> int:
    metadata = candidate.get("metadata")
    if not isinstance(metadata, Mapping):
        return 0
    return _positive_int(metadata.get("memory_record_id"))


def retrieve_class_commentary_memory_context(
    *,
    generation: Mapping[str, object],
    live_student_ids: Iterable[int],
    record_loader: Callable[[list[int]], list[dict]],
    memory_service: Optional[ClassCommentaryMemoryService] = None,
    reconciliation_marker: Optional[Callable[[int, list[int], str], object]] = None,
) -> dict:
    service = memory_service or ClassCommentaryMemoryService()
    if not service.enabled:
        return empty_class_commentary_memory_context("memory_disabled")

    organization_id = _positive_int(generation.get("organization_id"))
    skill_registry_id = _positive_int(generation.get("skill_registry_id"))
    subject_key = str(generation.get("subject_key") or "").strip()
    transcript = str(generation.get("confirmed_transcript_snapshot") or "").strip()
    roster = []
    for item in _json_list(generation.get("attending_roster_snapshot_json")):
        if not isinstance(item, Mapping):
            continue
        student_id = _positive_int(item.get("student_id"))
        student_name = str(item.get("student_name") or "").strip()
        if student_id and student_name:
            roster.append({"student_id": student_id, "student_name": student_name})
    live_ids = {_positive_int(item) for item in live_student_ids}
    live_ids.discard(0)
    mentioned_roster = [
        item
        for item in roster
        if item["student_id"] in live_ids and item["student_name"] in transcript
    ]
    if not organization_id or not skill_registry_id:
        return empty_class_commentary_memory_context("generation_scope_unavailable")

    style_candidates = []
    student_candidates: list[tuple[dict, dict]] = []
    try:
        style_candidates = service.search_style(
            transcript[:2000],
            organization_id=organization_id,
            scope_skill_registry_id=skill_registry_id,
        )
        if subject_key:
            for student in mentioned_roster:
                candidates = service.search_student(
                    transcript[:2000],
                    organization_id=organization_id,
                    student_id=student["student_id"],
                    subject_key=subject_key,
                )
                student_candidates.extend((candidate, student) for candidate in candidates)
    except Exception as exc:
        return empty_class_commentary_memory_context(
            f"mem0_{type(exc).__name__}"
        )

    candidate_ids = sorted({
        record_id
        for record_id in (
            *(_candidate_record_id(item) for item in style_candidates),
            *(_candidate_record_id(item) for item, _ in student_candidates),
        )
        if record_id
    })
    records = _record_map(record_loader(candidate_ids)) if candidate_ids else {}
    invalid_ids = set()
    accepted_style = []
    accepted_student = []
    seen = set()
    char_limit = int(service.settings.context_char_limit)
    used_chars = 0

    def accept_candidate(candidate: Mapping[str, object], *, student: Optional[dict] = None) -> None:
        nonlocal used_chars
        metadata = candidate.get("metadata")
        if not isinstance(metadata, Mapping):
            return
        record_id = _candidate_record_id(candidate)
        record = records.get(record_id)
        if not record:
            invalid_ids.add(record_id)
            return
        memory_type = "student_fact" if student else "teacher_style"
        scope_is_valid = (
            _positive_int(record.get("organization_id")) == organization_id
            and str(record.get("memory_type") or "") == memory_type
            and str(record.get("desired_status") or "") == "active"
            and _positive_int(record.get("record_version"))
            == _positive_int(metadata.get("record_version"))
            and _positive_int(record.get("active_evidence_count")) > 0
        )
        if student:
            scope_is_valid = (
                scope_is_valid
                and _positive_int(record.get("student_id")) == student["student_id"]
                and str(record.get("subject_key") or "") == subject_key
                and record.get("scope_skill_registry_id") is None
            )
        else:
            scope_is_valid = (
                scope_is_valid
                and _positive_int(record.get("scope_skill_registry_id")) == skill_registry_id
                and record.get("student_id") is None
            )
        try:
            confidence = float(record.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0
        if not scope_is_valid:
            invalid_ids.add(record_id)
            return
        if confidence < CLASS_COMMENTARY_MEMORY_MIN_CONFIDENCE:
            return
        memory_text = str(record.get("memory_text") or "").strip()
        dedupe_key = (memory_type, memory_text.casefold())
        if not memory_text or dedupe_key in seen or used_chars + len(memory_text) > char_limit:
            return
        seen.add(dedupe_key)
        used_chars += len(memory_text)
        item = {
            "memory_record_id": record_id,
            "mem0_memory_id": str(candidate.get("id") or ""),
            "memory_text": memory_text,
            "confidence": confidence,
            "record_version": _positive_int(record.get("record_version")),
            "created_from_revision_id": _positive_int(
                record.get("created_from_revision_id")
            ),
        }
        if student:
            item.update(student)
            accepted_student.append(item)
        else:
            accepted_style.append(item)

    for candidate in style_candidates:
        accept_candidate(candidate)
    for candidate, student in student_candidates:
        accept_candidate(candidate, student=student)

    invalid_ids.discard(0)
    if invalid_ids and reconciliation_marker:
        reconciliation_marker(
            organization_id,
            sorted(invalid_ids),
            "retrieval_projection_mismatch",
        )
    records_snapshot = [
        {
            "memory_record_id": item["memory_record_id"],
            "mem0_memory_id": item["mem0_memory_id"],
            "record_version": item["record_version"],
            "created_from_revision_id": item["created_from_revision_id"],
            "memory_type": "teacher_style",
            "memory_text": item["memory_text"],
        }
        for item in accepted_style
    ] + [
        {
            "memory_record_id": item["memory_record_id"],
            "mem0_memory_id": item["mem0_memory_id"],
            "record_version": item["record_version"],
            "created_from_revision_id": item["created_from_revision_id"],
            "memory_type": "student_fact",
            "student_id": item["student_id"],
            "memory_text": item["memory_text"],
        }
        for item in accepted_student
    ]
    rendered_lines = [
        *(f"Teacher style: {item['memory_text']}" for item in accepted_style),
        *(
            f"Student history ({item['student_name']}): {item['memory_text']}"
            for item in accepted_student
        ),
    ]
    return {
        "records": records_snapshot,
        "rendered_text": "\n".join(rendered_lines),
        "student_history_memories": accepted_student,
        "teacher_style_memories": accepted_style,
        "retrieval_status": "ready" if records_snapshot else "empty",
        "degraded_reason": "",
    }
