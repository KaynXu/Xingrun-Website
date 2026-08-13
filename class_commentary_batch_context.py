from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Optional

from class_commentary import (
    CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4,
    CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3,
    build_class_commentary_chat_request,
)
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
    validate_class_commentary_structured_generation_contract,
)
from class_commentary_graph_retrieval import (
    ClassCommentaryStudentGraphRetrievalError,
    retrieve_isolated_student_graph_context,
    validate_isolated_student_graph_context_snapshot,
)
from class_commentary_memory_retrieval import (
    ClassCommentaryStudentMemoryRetrievalError,
    retrieve_isolated_student_memory_context,
    validate_isolated_student_memory_context_snapshot,
)
from class_commentary_student_memory_v2 import (
    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V3,
    ClassCommentaryStudentEvidenceAttributionError,
    build_safe_class_context,
    build_student_current_evidence,
    build_student_evidence_assignment,
    canonical_hash,
    content_hash,
)
BATCH_ISOLATED_CONTEXT_SCHEMA_V1 = "class_commentary.batch_isolated_context.v1"
BATCH_ISOLATED_CONTEXT_MAX_UTF8_BYTES = 196_608


class ClassCommentaryBatchContextError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = str(code)


def _json_value(value: object, *, code: str) -> object:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ClassCommentaryBatchContextError(code) from exc


def _positive_int(value: object) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 0
    return normalized if normalized > 0 else 0


def _eligible_student_ids(generation: Mapping[str, object]) -> list[int]:
    values = _json_value(
        generation.get("eligible_student_ids_json"),
        code="batch_context_scope_invalid",
    )
    if (
        not isinstance(values, list)
        or not values
        or any(type(value) is not int or value <= 0 for value in values)
        or len(set(values)) != len(values)
    ):
        raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
    return list(values)


def _frozen_roster(
    generation: Mapping[str, object],
    field_name: str,
    *,
    require_eligible_order: bool,
) -> list[dict]:
    values = _json_value(
        generation.get(field_name),
        code="batch_context_scope_invalid",
    )
    if not isinstance(values, list) or not values:
        raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
    normalized = []
    seen_ids = set()
    seen_names = set()
    for item in values:
        if not isinstance(item, Mapping):
            raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
        student_id = _positive_int(item.get("student_id"))
        student_name = str(item.get("student_name") or "").strip()
        if (
            not student_id
            or not student_name
            or student_id in seen_ids
            or student_name in seen_names
        ):
            raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
        seen_ids.add(student_id)
        seen_names.add(student_name)
        normalized.append(
            {"student_id": student_id, "student_name": student_name}
        )
    eligible_ids = _eligible_student_ids(generation)
    if require_eligible_order:
        if [item["student_id"] for item in normalized] != eligible_ids:
            raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
    elif not set(eligible_ids).issubset(seen_ids):
        raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
    return normalized


def parse_frozen_batch_generation_inputs(
    generation: Mapping[str, object],
) -> dict:
    if (
        str(generation.get("student_history_memory_mode") or "")
        != CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
    ):
        raise ClassCommentaryBatchContextError("batch_context_mode_invalid")
    try:
        validate_class_commentary_structured_generation_contract(generation)
    except ValueError as exc:
        raise ClassCommentaryBatchContextError(
            "batch_context_snapshot_invalid"
        ) from exc
    attending_roster = _frozen_roster(
        generation,
        "attending_roster_snapshot_json",
        require_eligible_order=True,
    )
    privacy_roster = _frozen_roster(
        generation,
        "privacy_roster_snapshot_json",
        require_eligible_order=False,
    )
    response_format = _json_value(
        generation.get("response_format_json"),
        code="batch_context_snapshot_invalid",
    )
    model_parameters = _json_value(
        generation.get("model_parameters_json"),
        code="batch_context_snapshot_invalid",
    )
    if (
        not isinstance(response_format, dict)
        or not isinstance(model_parameters, dict)
        or set(model_parameters) != {"temperature"}
        or type(model_parameters.get("temperature")) not in {int, float}
    ):
        raise ClassCommentaryBatchContextError("batch_context_snapshot_invalid")
    class_name = str(generation.get("class_name_snapshot") or "").strip()
    skill_id = str(generation.get("skill_id") or "").strip()
    skill_name = str(generation.get("skill_name_snapshot") or "").strip()
    skill_content = str(generation.get("skill_content_snapshot") or "").strip()
    transcript = str(
        generation.get("confirmed_transcript_snapshot") or ""
    ).strip()
    if (
        not _positive_int(generation.get("class_id"))
        or not class_name
        or not skill_id
        or not skill_name
        or not skill_content
        or not transcript
    ):
        raise ClassCommentaryBatchContextError("batch_context_snapshot_invalid")
    return {
        "class_record": {
            "id": int(generation["class_id"]),
            "name": class_name,
        },
        "students": [
            {
                "id": item["student_id"],
                "name": item["student_name"],
            }
            for item in attending_roster
        ],
        "attending_roster": attending_roster,
        "privacy_roster": privacy_roster,
        "eligible_student_ids": _eligible_student_ids(generation),
        "transcript_text": transcript,
        "skill": {
            "id": skill_id,
            "name": skill_name,
            "content": skill_content,
        },
        "feedback_schema_version": str(
            generation.get("feedback_schema_version") or ""
        ),
        "prompt_version": str(generation.get("prompt_version") or ""),
        "response_format": response_format,
        "model_parameters": model_parameters,
    }


def _normalized_roster(
    generation: Mapping[str, object],
    attending_roster: list[dict],
) -> list[dict]:
    expected_ids = _eligible_student_ids(generation)
    normalized = []
    seen_ids = set()
    for item in attending_roster:
        if not isinstance(item, Mapping):
            raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
        student_id = _positive_int(item.get("student_id") or item.get("id"))
        student_name = str(
            item.get("student_name") or item.get("name") or ""
        ).strip()
        if not student_id or not student_name or student_id in seen_ids:
            raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
        seen_ids.add(student_id)
        normalized.append(
            {"student_id": student_id, "student_name": student_name}
        )
    if [item["student_id"] for item in normalized] != expected_ids:
        raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
    return normalized


def _teacher_style_prompt_items(student_contexts: list[dict]) -> list[dict]:
    records_by_id: dict[int, dict] = {}
    ordered_record_ids: list[int] = []
    for partition in student_contexts:
        memory_context = partition.get("memory_context")
        if not isinstance(memory_context, Mapping):
            raise ClassCommentaryBatchContextError("batch_memory_context_invalid")
        for item in memory_context.get("teacher_style_memories") or []:
            if not isinstance(item, Mapping):
                raise ClassCommentaryBatchContextError(
                    "batch_memory_context_invalid"
                )
            record_id = _positive_int(item.get("memory_record_id"))
            memory_text = str(item.get("memory_text") or "").strip()
            if not record_id or not memory_text:
                raise ClassCommentaryBatchContextError(
                    "batch_memory_context_invalid"
                )
            normalized = dict(item)
            existing = records_by_id.get(record_id)
            if existing is not None and existing != normalized:
                raise ClassCommentaryBatchContextError(
                    "batch_memory_context_invalid"
                )
            if existing is None:
                records_by_id[record_id] = normalized
                ordered_record_ids.append(record_id)
    result = []
    seen_text = set()
    for record_id in ordered_record_ids:
        memory_text = str(records_by_id[record_id]["memory_text"]).strip()
        dedupe_key = memory_text.casefold()
        if dedupe_key in seen_text:
            continue
        seen_text.add(dedupe_key)
        result.append({"style_rule": memory_text})
    return result


def build_batch_isolated_teacher_style_memories(
    memory_context: Mapping[str, object],
) -> list[dict]:
    items = memory_context.get("teacher_style_memories")
    if not isinstance(items, list):
        raise ClassCommentaryBatchContextError("batch_memory_context_invalid")
    result = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ClassCommentaryBatchContextError("batch_memory_context_invalid")
        memory_text = str(item.get("style_rule") or "").strip()
        if not memory_text or set(item) != {"style_rule"}:
            raise ClassCommentaryBatchContextError("batch_memory_context_invalid")
        result.append({"style_rule": memory_text})
    return result


def _validate_batch_context_size(value: object) -> None:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ClassCommentaryBatchContextError(
            "batch_context_snapshot_invalid"
        ) from exc
    if len(serialized.encode("utf-8")) > BATCH_ISOLATED_CONTEXT_MAX_UTF8_BYTES:
        raise ClassCommentaryBatchContextError("batch_context_too_large")


def build_batch_isolated_prompt_student_contexts(
    memory_context: Mapping[str, object],
) -> list[dict]:
    partitions = memory_context.get("student_contexts_by_id")
    if not isinstance(partitions, list):
        raise ClassCommentaryBatchContextError("batch_context_snapshot_invalid")
    result = []
    for partition in partitions:
        if not isinstance(partition, Mapping):
            raise ClassCommentaryBatchContextError("batch_context_snapshot_invalid")
        student_id = _positive_int(partition.get("student_id"))
        raw_memory = partition.get("memory_context")
        graph_context = partition.get("learning_graph")
        if (
            not student_id
            or not isinstance(raw_memory, Mapping)
            or not isinstance(graph_context, Mapping)
        ):
            raise ClassCommentaryBatchContextError("batch_context_snapshot_invalid")
        historical_items = []
        for item in raw_memory.get("student_history_memories") or []:
            if not isinstance(item, Mapping):
                raise ClassCommentaryBatchContextError(
                    "batch_memory_context_invalid"
                )
            memory_text = str(item.get("memory_text") or "").strip()
            if not memory_text:
                raise ClassCommentaryBatchContextError(
                    "batch_memory_context_invalid"
                )
            historical_items.append(
                {
                    "historical_context": memory_text,
                    "source_time": str(item.get("created_at") or ""),
                }
            )
        result.append(
            {
                "student_id": student_id,
                "current_student_evidence": {
                    "verified_fragments": [
                        {
                            "start": item["start"],
                            "end": item["end"],
                            "text": item["text"],
                            "text_hash": item["text_hash"],
                        }
                        for item in partition["current_evidence_snapshot"].get(
                            "fragments", []
                        )
                    ]
                },
                "memory_retrieval_status": str(
                    raw_memory.get("retrieval_status") or "empty"
                ),
                "student_history_memories": historical_items,
                "learning_graph": {
                    "retrieval_status": str(
                        graph_context.get("retrieval_status") or ""
                    ),
                    "current_states": list(
                        graph_context.get("current_states") or []
                    ),
                    "recent_changes": list(
                        graph_context.get("recent_changes") or []
                    ),
                    "allowed_evidence_refs": [
                        str(value)
                        for value in graph_context.get("allowed_evidence_refs") or []
                        if isinstance(value, str) and value
                    ],
                },
            }
        )
    return result


def build_batch_generation_execution_snapshot(
    *,
    generation: Mapping[str, object],
    record_loader: Callable[[list[int]], list[dict]],
    memory_service,
    runtime_config: Optional[Mapping[str, object]] = None,
    reconciliation_marker: Optional[Callable[[int, list[int], str], object]] = None,
    graph_adapter=None,
    graph_summary_loader: Optional[Callable[..., dict]] = None,
) -> dict:
    frozen = parse_frozen_batch_generation_inputs(generation)
    prompt_version = frozen["prompt_version"]
    try:
        evidence_assignment = (
            build_student_evidence_assignment(
                transcript=frozen["transcript_text"],
                transcript_hash=str(
                    generation.get("confirmed_transcript_hash") or ""
                ),
                roster=frozen["privacy_roster"],
                attending_student_ids=frozen["eligible_student_ids"],
            )
            if prompt_version
            == CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4
            else None
        )
        memory_context = build_batch_isolated_memory_context(
            generation=generation,
            attending_roster=frozen["attending_roster"],
            evidence_roster=frozen["privacy_roster"],
            record_loader=record_loader,
            memory_service=memory_service,
            runtime_config=runtime_config,
            reconciliation_marker=reconciliation_marker,
            graph_adapter=graph_adapter,
            graph_summary_loader=graph_summary_loader,
            evidence_assignment=evidence_assignment,
        )
    except ClassCommentaryBatchContextError:
        raise
    except ClassCommentaryStudentEvidenceAttributionError:
        raise
    except ValueError as exc:
        raise ClassCommentaryBatchContextError(
            "batch_context_snapshot_invalid"
        ) from exc
    chat_request = build_class_commentary_chat_request(
        class_record=frozen["class_record"],
        students=frozen["students"],
        transcript_text=frozen["transcript_text"],
        skill=frozen["skill"],
        teacher_style_memories=build_batch_isolated_teacher_style_memories(
            memory_context
        ),
        student_history_memories=[],
        feedback_schema_version=frozen["feedback_schema_version"],
        eligible_student_ids=frozen["eligible_student_ids"],
        prompt_version=frozen["prompt_version"],
        response_format=frozen["response_format"],
        student_history_memory_mode=(
            CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
        ),
        student_contexts_by_id=build_batch_isolated_prompt_student_contexts(
            memory_context
        ),
        official_course_roster=(
            [
                {"id": item["student_id"], "name": item["student_name"]}
                for item in frozen["privacy_roster"]
            ]
            if prompt_version
            == CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5
            else None
        ),
    )
    chat_request["temperature"] = float(frozen["model_parameters"]["temperature"])
    return {
        **frozen,
        "prompt_payload": chat_request,
        "memory_context": memory_context,
    }


def build_batch_isolated_memory_context(
    *,
    generation: Mapping[str, object],
    attending_roster: list[dict],
    evidence_roster: Optional[list[dict]] = None,
    record_loader: Callable[[list[int]], list[dict]],
    memory_service,
    runtime_config: Optional[Mapping[str, object]] = None,
    reconciliation_marker: Optional[Callable[[int, list[int], str], object]] = None,
    graph_adapter=None,
    graph_summary_loader: Optional[Callable[..., dict]] = None,
    evidence_assignment: Optional[Mapping[str, object]] = None,
) -> dict:
    roster = _normalized_roster(generation, attending_roster)
    attribution_roster = list(evidence_roster or roster)
    transcript = str(generation.get("confirmed_transcript_snapshot") or "")
    transcript_hash = str(generation.get("confirmed_transcript_hash") or "")
    class_context = build_safe_class_context(
        class_record={"id": int(generation.get("class_id") or 0)},
        subject_key=str(generation.get("subject_key") or ""),
    )
    prompt_version = str(generation.get("prompt_version") or "")
    if prompt_version and prompt_version not in {
        CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4,
        CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5,
    }:
        raise ClassCommentaryBatchContextError("batch_context_snapshot_invalid")
    use_model_attribution = (
        prompt_version == CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5
    )
    assignment = None
    if not use_model_attribution:
        assignment = (
            dict(evidence_assignment)
            if isinstance(evidence_assignment, Mapping)
            else build_student_evidence_assignment(
                transcript=transcript,
                transcript_hash=transcript_hash,
                roster=attribution_roster,
                attending_student_ids=[item["student_id"] for item in roster],
            )
        )
    partitions = []
    try:
        for student in roster:
            student_id = int(student["student_id"])
            evidence_snapshot = build_student_current_evidence(
                transcript=transcript,
                transcript_hash=transcript_hash,
                roster=attribution_roster,
                target_student_id=student_id,
                matcher_version=(
                    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2
                    if use_model_attribution
                    else CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V3
                ),
                assignment=assignment,
            )
            memory_snapshot = retrieve_isolated_student_memory_context(
                generation=generation,
                student_id=student_id,
                evidence_snapshot=evidence_snapshot,
                class_context=class_context,
                record_loader=record_loader,
                memory_service=memory_service,
                reconciliation_marker=reconciliation_marker,
                student_history_memory_mode=(
                    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
                ),
            )
            graph_snapshot = retrieve_isolated_student_graph_context(
                generation=generation,
                student_id=student_id,
                class_context=class_context,
                runtime_config=runtime_config,
                graph_adapter=graph_adapter,
                summary_loader=graph_summary_loader,
                require_available=True,
            )
            partitions.append(
                {
                    "student_id": student_id,
                    "class_context": class_context,
                    "current_evidence_snapshot": evidence_snapshot,
                    "memory_context": memory_snapshot,
                    "learning_graph": graph_snapshot,
                }
            )
    except ClassCommentaryStudentEvidenceAttributionError:
        raise
    except (
        ClassCommentaryStudentMemoryRetrievalError,
        ClassCommentaryStudentGraphRetrievalError,
        ValueError,
    ) as exc:
        raise ClassCommentaryBatchContextError(
            "batch_context_retrieval_failed"
        ) from exc
    context = {
        "schema_version": BATCH_ISOLATED_CONTEXT_SCHEMA_V1,
        "student_history_memory_mode": (
            CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
        ),
        "teacher_style_memories": _teacher_style_prompt_items(partitions),
        "student_contexts_by_id": partitions,
    }
    validate_batch_isolated_memory_context_snapshot(
        generation=generation,
        memory_context=context,
        record_loader=record_loader,
        runtime_config=runtime_config,
        graph_adapter=graph_adapter,
        graph_summary_loader=graph_summary_loader,
    )
    return context


def _validate_current_evidence_snapshot(
    *,
    generation: Mapping[str, object],
    evidence_snapshot: Mapping[str, object],
) -> None:
    if set(evidence_snapshot) != {
        "schema_version",
        "matcher_version",
        "transcript_hash",
        "attribution",
        "fragments",
        "snapshot_hash",
    }:
        raise ClassCommentaryBatchContextError("batch_evidence_snapshot_invalid")
    snapshot_without_hash = {
        key: value for key, value in evidence_snapshot.items() if key != "snapshot_hash"
    }
    prompt_version = str(generation.get("prompt_version") or "")
    expected_matcher_version = (
        CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2
        if prompt_version == CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5
        else CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V3
    )
    expected_attribution = (
        "fail_closed_no_structured_ownership"
        if expected_matcher_version == CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2
        else "unique_clause_owner_v3"
    )
    fragments = evidence_snapshot.get("fragments")
    if (
        str(evidence_snapshot.get("schema_version") or "")
        != "class_commentary.student_current_evidence.v1"
        or str(evidence_snapshot.get("matcher_version") or "")
        != expected_matcher_version
        or str(evidence_snapshot.get("transcript_hash") or "")
        != str(generation.get("confirmed_transcript_hash") or "")
        or str(evidence_snapshot.get("attribution") or "")
        != expected_attribution
        or not isinstance(fragments, list)
        or (
            expected_matcher_version == CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2
            and fragments
        )
        or (
            expected_matcher_version == CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V3
            and not fragments
        )
        or str(evidence_snapshot.get("snapshot_hash") or "")
        != canonical_hash(snapshot_without_hash)
    ):
        raise ClassCommentaryBatchContextError("batch_evidence_snapshot_invalid")
    transcript = str(generation.get("confirmed_transcript_snapshot") or "")
    previous_end = -1
    for fragment in fragments:
        if not isinstance(fragment, Mapping) or set(fragment) != {
            "start", "end", "text", "text_hash"
        }:
            raise ClassCommentaryBatchContextError("batch_evidence_snapshot_invalid")
        start = fragment.get("start")
        end = fragment.get("end")
        text = str(fragment.get("text") or "")
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
            or start < previous_end
            or transcript[start:end] != text
            or content_hash(text) != str(fragment.get("text_hash") or "")
        ):
            raise ClassCommentaryBatchContextError("batch_evidence_snapshot_invalid")
        previous_end = end


def _validate_partition_memory_shape(
    *, student_id: int, memory_context: Mapping[str, object]
) -> None:
    records = memory_context.get("records")
    teacher_style = memory_context.get("teacher_style_memories")
    student_history = memory_context.get("student_history_memories")
    if (
        not isinstance(records, list)
        or not isinstance(teacher_style, list)
        or not isinstance(student_history, list)
        or records != [*teacher_style, *student_history]
        or str(memory_context.get("student_history_memory_mode") or "")
        != CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
    ):
        raise ClassCommentaryBatchContextError("batch_memory_context_invalid")
    record_ids = []
    for item in teacher_style:
        if (
            not isinstance(item, Mapping)
            or str(item.get("memory_type") or "") != "teacher_style"
            or item.get("student_id") is not None
        ):
            raise ClassCommentaryBatchContextError("batch_memory_context_invalid")
        record_ids.append(_positive_int(item.get("memory_record_id")))
    for item in student_history:
        if (
            not isinstance(item, Mapping)
            or str(item.get("memory_type") or "") != "student_fact"
            or _positive_int(item.get("student_id")) != int(student_id)
        ):
            raise ClassCommentaryBatchContextError("batch_memory_context_invalid")
        record_ids.append(_positive_int(item.get("memory_record_id")))
    if any(not record_id for record_id in record_ids) or len(set(record_ids)) != len(
        record_ids
    ):
        raise ClassCommentaryBatchContextError("batch_memory_context_invalid")


def validate_batch_isolated_memory_context_snapshot(
    *,
    generation: Mapping[str, object],
    memory_context: Mapping[str, object],
    record_loader: Callable[[list[int]], list[dict]],
    runtime_config: Optional[Mapping[str, object]] = None,
    graph_adapter=None,
    graph_summary_loader: Optional[Callable[..., dict]] = None,
) -> None:
    if (
        set(memory_context)
        != {
            "schema_version",
            "student_history_memory_mode",
            "teacher_style_memories",
            "student_contexts_by_id",
        }
        or str(memory_context.get("schema_version") or "")
        != BATCH_ISOLATED_CONTEXT_SCHEMA_V1
        or str(memory_context.get("student_history_memory_mode") or "")
        != CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
    ):
        raise ClassCommentaryBatchContextError("batch_context_snapshot_invalid")
    expected_ids = _eligible_student_ids(generation)
    partitions = memory_context.get("student_contexts_by_id")
    if not isinstance(partitions, list):
        raise ClassCommentaryBatchContextError("batch_context_snapshot_invalid")
    actual_ids = [
        _positive_int(item.get("student_id")) if isinstance(item, Mapping) else 0
        for item in partitions
    ]
    if actual_ids != expected_ids or len(set(actual_ids)) != len(actual_ids):
        raise ClassCommentaryBatchContextError("batch_context_scope_invalid")
    try:
        for partition in partitions:
            if not isinstance(partition, Mapping) or set(partition) != {
                "student_id",
                "class_context",
                "current_evidence_snapshot",
                "memory_context",
                "learning_graph",
            }:
                raise ClassCommentaryBatchContextError(
                    "batch_context_snapshot_invalid"
                )
            student_id = int(partition["student_id"])
            class_context = partition["class_context"]
            evidence_snapshot = partition["current_evidence_snapshot"]
            student_memory = partition["memory_context"]
            graph_context = partition["learning_graph"]
            if (
                not isinstance(class_context, Mapping)
                or dict(class_context)
                != {"subject_key": str(generation.get("subject_key") or "").strip()}
                or not isinstance(evidence_snapshot, Mapping)
                or not isinstance(student_memory, Mapping)
                or not isinstance(graph_context, Mapping)
            ):
                raise ClassCommentaryBatchContextError(
                    "batch_context_snapshot_invalid"
                )
            _validate_current_evidence_snapshot(
                generation=generation,
                evidence_snapshot=evidence_snapshot,
            )
            _validate_partition_memory_shape(
                student_id=student_id,
                memory_context=student_memory,
            )
            validate_isolated_student_memory_context_snapshot(
                generation=generation,
                student_id=student_id,
                memory_context=student_memory,
                record_loader=record_loader,
                expected_memory_mode=(
                    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
                ),
            )
            validate_isolated_student_graph_context_snapshot(
                generation=generation,
                student_id=student_id,
                graph_context=graph_context,
                class_context=class_context,
                summary_loader=graph_summary_loader,
                runtime_config=runtime_config,
                graph_adapter=graph_adapter,
                revalidate_semantica=True,
                require_available=True,
            )
    except ClassCommentaryBatchContextError:
        raise
    except (
        ClassCommentaryStudentMemoryRetrievalError,
        ClassCommentaryStudentGraphRetrievalError,
        ValueError,
    ) as exc:
        raise ClassCommentaryBatchContextError(
            "batch_context_snapshot_invalid"
        ) from exc
    if memory_context.get("teacher_style_memories") != _teacher_style_prompt_items(
        list(partitions)
    ):
        raise ClassCommentaryBatchContextError("batch_memory_context_invalid")
    build_batch_isolated_teacher_style_memories(memory_context)
    build_batch_isolated_prompt_student_contexts(memory_context)
    _validate_batch_context_size(memory_context)
