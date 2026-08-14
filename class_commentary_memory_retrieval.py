from __future__ import annotations

import json
import logging
from typing import Callable, Iterable, Mapping, Optional

from class_commentary_memory import ClassCommentaryMemoryService
from class_commentary_student_memory_v2 import build_student_memory_query

logger = logging.getLogger(__name__)


CLASS_COMMENTARY_MEMORY_MIN_CONFIDENCE = 0.7


class ClassCommentaryStudentMemoryRetrievalError(RuntimeError):
    pass


def empty_class_commentary_memory_context(
    reason: str = "",
    *,
    student_history_memory_mode: str = "",
) -> dict:
    context = {
        "records": [],
        "rendered_text": "",
        "student_history_memories": [],
        "teacher_style_memories": [],
        "retrieval_status": "degraded" if reason else "empty",
        "degraded_reason": str(reason or ""),
    }
    if student_history_memory_mode:
        context["student_history_memory_mode"] = student_history_memory_mode
    return context


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
    student_history_memory_mode = str(
        generation.get("student_history_memory_mode") or ""
    )
    student_history_disabled = student_history_memory_mode == "disabled_v1"
    service = memory_service or ClassCommentaryMemoryService()
    if not service.enabled:
        return empty_class_commentary_memory_context(
            "memory_disabled",
            student_history_memory_mode=student_history_memory_mode,
        )

    organization_id = _positive_int(generation.get("organization_id"))
    skill_registry_id = _positive_int(generation.get("skill_registry_id"))
    subject_key = str(generation.get("subject_key") or "").strip()
    transcript = str(generation.get("confirmed_transcript_snapshot") or "").strip()
    mentioned_roster = []
    if not student_history_disabled:
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
        logger.warning(
            "class commentary memory retrieval degraded: generation_scope_unavailable (org=%s skill=%s)",
            organization_id,
            skill_registry_id,
        )
        return empty_class_commentary_memory_context(
            "generation_scope_unavailable",
            student_history_memory_mode=student_history_memory_mode,
        )

    style_candidates = []
    student_candidates: list[tuple[dict, dict]] = []
    query_char_limit = max(1, int(getattr(service.settings, "search_query_char_limit", 2000) or 2000))
    search_query = transcript[:query_char_limit]
    try:
        style_candidates = service.search_style(
            search_query,
            organization_id=organization_id,
            scope_skill_registry_id=skill_registry_id,
        )
        if subject_key and not student_history_disabled:
            for student in mentioned_roster:
                candidates = service.search_student(
                    search_query,
                    organization_id=organization_id,
                    student_id=student["student_id"],
                    subject_key=subject_key,
                )
                student_candidates.extend((candidate, student) for candidate in candidates)
    except Exception as exc:
        logger.warning(
            "class commentary memory retrieval degraded (org=%s skill=%s): %s",
            organization_id,
            skill_registry_id,
            type(exc).__name__,
            exc_info=True,
        )
        return empty_class_commentary_memory_context(
            f"mem0_{type(exc).__name__}",
            student_history_memory_mode=student_history_memory_mode,
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
    context = {
        "records": records_snapshot,
        "rendered_text": "\n".join(rendered_lines),
        "student_history_memories": accepted_student,
        "teacher_style_memories": accepted_style,
        "retrieval_status": "ready" if records_snapshot else "empty",
        "degraded_reason": "",
    }
    if student_history_memory_mode:
        context["student_history_memory_mode"] = student_history_memory_mode
    return context


def retrieve_isolated_student_memory_context(
    *,
    generation: Mapping[str, object],
    student_id: int,
    evidence_snapshot: Mapping[str, object],
    class_context: Mapping[str, object],
    record_loader: Callable[[list[int]], list[dict]],
    memory_service: Optional[ClassCommentaryMemoryService] = None,
    reconciliation_marker: Optional[Callable[[int, list[int], str], object]] = None,
    student_history_memory_mode: str = "isolated_v2",
) -> dict:
    organization_id = _positive_int(generation.get("organization_id"))
    skill_registry_id = _positive_int(generation.get("skill_registry_id"))
    subject_key = str(generation.get("subject_key") or "").strip()
    target_student_id = _positive_int(student_id)
    if not organization_id or not skill_registry_id or not target_student_id:
        raise ClassCommentaryStudentMemoryRetrievalError(
            "isolated_generation_scope_unavailable"
        )
    if not subject_key:
        raise ClassCommentaryStudentMemoryRetrievalError(
            "subject_unavailable"
        )
    service = memory_service or ClassCommentaryMemoryService()
    if not service.enabled:
        raise ClassCommentaryStudentMemoryRetrievalError("memory_disabled")
    query = build_student_memory_query(
        evidence_snapshot=evidence_snapshot,
        class_context=class_context,
    )
    try:
        style_candidates = service.search_style(
            query,
            organization_id=organization_id,
            scope_skill_registry_id=skill_registry_id,
        )
        student_candidates = service.search_student(
            query,
            organization_id=organization_id,
            student_id=target_student_id,
            subject_key=subject_key,
        )
    except Exception as exc:
        logger.warning(
            "class commentary isolated memory retrieval failed (org=%s skill=%s student=%s): %s",
            organization_id,
            skill_registry_id,
            target_student_id,
            type(exc).__name__,
            exc_info=True,
        )
        raise ClassCommentaryStudentMemoryRetrievalError(
            f"mem0_{type(exc).__name__}"
        ) from exc
    candidate_ids = sorted(
        {
            _candidate_record_id(candidate)
            for candidate in [*style_candidates, *student_candidates]
            if _candidate_record_id(candidate)
        }
    )
    records = _record_map(record_loader(candidate_ids)) if candidate_ids else {}
    invalid_ids = set()
    accepted_style = []
    accepted_student = []
    used_chars = 0
    char_limit = int(service.settings.context_char_limit)
    style_limit = max(1, int(getattr(service.settings, "style_limit", 5) or 5))
    student_limit = max(1, int(getattr(service.settings, "student_limit", 5) or 5))

    def accept(candidate: Mapping[str, object], *, memory_type: str) -> None:
        nonlocal used_chars
        metadata = candidate.get("metadata")
        if not isinstance(metadata, Mapping):
            return
        record_id = _candidate_record_id(candidate)
        record = records.get(record_id)
        if not record:
            invalid_ids.add(record_id)
            return
        active_evidence = record.get("active_evidence")
        scope_valid = (
            _positive_int(metadata.get("organization_id")) == organization_id
            and str(metadata.get("memory_type") or "") == memory_type
            and str(metadata.get("status") or "") == "active"
            and _positive_int(record.get("organization_id")) == organization_id
            and str(record.get("memory_type") or "") == memory_type
            and str(record.get("desired_status") or "") == "active"
            and str(record.get("applied_status") or "") == "active"
            and str(record.get("mem0_memory_id") or "")
            == str(candidate.get("id") or "")
            and _positive_int(record.get("record_version"))
            == _positive_int(metadata.get("record_version"))
            and isinstance(active_evidence, list)
            and bool(active_evidence)
            and _positive_int(record.get("active_evidence_count"))
            == len(active_evidence)
            and _positive_int(metadata.get("evidence_count"))
            == len(active_evidence)
        )
        if memory_type == "student_fact":
            scope_valid = (
                scope_valid
                and _positive_int(metadata.get("student_id")) == target_student_id
                and str(metadata.get("subject_key") or "") == subject_key
                and metadata.get("scope_skill_registry_id") is None
                and _positive_int(record.get("student_id")) == target_student_id
                and str(record.get("subject_key") or "") == subject_key
                and record.get("scope_skill_registry_id") is None
            )
        else:
            scope_valid = (
                scope_valid
                and _positive_int(metadata.get("scope_skill_registry_id"))
                == skill_registry_id
                and metadata.get("student_id") is None
                and metadata.get("subject_key") is None
                and _positive_int(record.get("scope_skill_registry_id"))
                == skill_registry_id
                and record.get("student_id") is None
                and record.get("subject_key") is None
            )
        if not scope_valid:
            invalid_ids.add(record_id)
            return
        try:
            confidence = float(record.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0
        memory_text = str(record.get("memory_text") or "").strip()
        if (
            confidence < CLASS_COMMENTARY_MEMORY_MIN_CONFIDENCE
            or not memory_text
            or used_chars + len(memory_text) > char_limit
        ):
            return
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
            "created_at": str(record.get("created_at") or ""),
            "active_evidence": list(active_evidence),
            "memory_type": memory_type,
        }
        if memory_type == "student_fact":
            item["student_id"] = target_student_id
            item["subject_key"] = subject_key
            accepted_student.append(item)
        else:
            item["scope_skill_registry_id"] = skill_registry_id
            accepted_style.append(item)

    for candidate in style_candidates[:style_limit]:
        accept(candidate, memory_type="teacher_style")
    for candidate in student_candidates[:student_limit]:
        accept(candidate, memory_type="student_fact")
    invalid_ids.discard(0)
    if invalid_ids and reconciliation_marker:
        reconciliation_marker(
            organization_id,
            sorted(invalid_ids),
            "retrieval_projection_mismatch",
        )
    records_snapshot = [*accepted_style, *accepted_student]
    return {
        "records": records_snapshot,
        "rendered_text": "",
        "student_history_memories": accepted_student,
        "teacher_style_memories": accepted_style,
        "retrieval_status": "ready" if records_snapshot else "empty",
        "degraded_reason": "",
        "student_history_memory_mode": str(student_history_memory_mode),
    }


def validate_isolated_student_memory_context_snapshot(
    *,
    generation: Mapping[str, object],
    student_id: int,
    memory_context: Mapping[str, object],
    record_loader: Callable[[list[int]], list[dict]],
    expected_memory_mode: str = "isolated_v2",
) -> None:
    organization_id = _positive_int(generation.get("organization_id"))
    skill_registry_id = _positive_int(generation.get("skill_registry_id"))
    target_student_id = _positive_int(student_id)
    subject_key = str(generation.get("subject_key") or "").strip()
    snapshot_records = memory_context.get("records")
    if (
        not isinstance(snapshot_records, list)
        or str(memory_context.get("student_history_memory_mode") or "")
        != str(expected_memory_mode)
    ):
        raise ClassCommentaryStudentMemoryRetrievalError("memory_snapshot_invalid")
    record_ids = sorted(
        {
            _positive_int(record.get("memory_record_id"))
            for record in snapshot_records
            if isinstance(record, Mapping)
        }
    )
    current_records = _record_map(record_loader(record_ids)) if record_ids else {}
    if len(current_records) != len(record_ids):
        raise ClassCommentaryStudentMemoryRetrievalError("memory_snapshot_stale")
    for snapshot in snapshot_records:
        if not isinstance(snapshot, Mapping):
            raise ClassCommentaryStudentMemoryRetrievalError("memory_snapshot_invalid")
        record_id = _positive_int(snapshot.get("memory_record_id"))
        current = current_records.get(record_id)
        memory_type = str(snapshot.get("memory_type") or "")
        active_evidence = current.get("active_evidence") if current else None
        valid = bool(
            current
            and _positive_int(current.get("organization_id")) == organization_id
            and str(current.get("memory_type") or "") == memory_type
            and str(current.get("desired_status") or "") == "active"
            and str(current.get("applied_status") or "") == "active"
            and str(current.get("mem0_memory_id") or "")
            == str(snapshot.get("mem0_memory_id") or "")
            and _positive_int(current.get("record_version"))
            == _positive_int(snapshot.get("record_version"))
            and str(current.get("memory_text") or "")
            == str(snapshot.get("memory_text") or "")
            and isinstance(active_evidence, list)
            and bool(active_evidence)
            and _positive_int(current.get("active_evidence_count"))
            == len(active_evidence)
            and active_evidence == snapshot.get("active_evidence")
            and _positive_int(current.get("created_from_revision_id"))
            == _positive_int(snapshot.get("created_from_revision_id"))
        )
        if memory_type == "student_fact":
            valid = bool(
                valid
                and _positive_int(current.get("student_id")) == target_student_id
                and str(current.get("subject_key") or "") == subject_key
                and current.get("scope_skill_registry_id") is None
            )
        elif memory_type == "teacher_style":
            valid = bool(
                valid
                and _positive_int(current.get("scope_skill_registry_id"))
                == skill_registry_id
                and current.get("student_id") is None
                and current.get("subject_key") is None
            )
        else:
            valid = False
        if not valid:
            raise ClassCommentaryStudentMemoryRetrievalError(
                "memory_snapshot_stale"
            )
