from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from class_commentary import (
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
    CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
    normalize_class_commentary_feedback_text,
)


CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1 = "class_commentary.student_feedback.v1"
CLASS_COMMENTARY_STUDENT_NAME_MATCHER_V1 = "class_commentary.student_name_matcher.v1"
CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1 = "class_commentary.attending_roster_scope.v1"
CLASS_COMMENTARY_STRUCTURED_RESPONSE_FORMAT = {"type": "json_object"}
CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_DISABLED_V1 = "disabled_v1"
CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT = 2000
CLASS_COMMENTARY_STUDENT_FEEDBACK_TOTAL_LIMIT = 30000


class ClassCommentaryStudentScopeError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ClassCommentaryStructuredFeedbackValidationError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        student_id: int | None = None,
        field: str = "",
        limit: int | None = None,
        reason: str = "",
    ):
        super().__init__(reason or code)
        self.code = code
        self.student_id = student_id
        self.field = field
        self.limit = limit
        self.reason = reason or code


class _StudentFeedbackItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    student_id: StrictInt
    feedback_text: StrictStr


class _StudentFeedbackEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1]
    items: list[_StudentFeedbackItemV1]


def _invalid_envelope(
    *,
    schema_version: str,
    stored_hash: str,
    derived_text: str,
) -> dict:
    return {
        "feedback_schema_version": schema_version,
        "feedback_schema_status": "invalid",
        "student_feedback_items": [],
        "structured_feedback_hash": stored_hash,
        "derived_feedback_text": derived_text,
        "writable": False,
    }


def _parse_json(value: object):
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value or ""))


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_match_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip()
    return re.sub(r"\s+", " ", normalized)


def _match_normalized_student_name_spans(
    text: str,
    normalized_roster: list[tuple[int, int, str]],
) -> list[tuple[int, int, int]]:
    candidates: list[tuple[int, int, int, int]] = []
    for position, student_id, student_name in normalized_roster:
        start = text.find(student_name)
        while start >= 0:
            candidates.append((start, start + len(student_name), position, student_id))
            start = text.find(student_name, start + 1)

    accepted_spans: list[tuple[int, int, int]] = []
    for start, end, _, student_id in sorted(
        candidates,
        key=lambda item: (-(item[1] - item[0]), item[0], item[2]),
    ):
        if any(
            start < accepted_end and end > accepted_start
            for accepted_start, accepted_end, _ in accepted_spans
        ):
            continue
        accepted_spans.append((start, end, student_id))
    return accepted_spans


def _normalize_class_commentary_scope_roster(
    roster: object,
) -> list[tuple[int, int, str]]:
    if not isinstance(roster, list):
        raise ValueError("structured feedback roster must be a list")
    normalized_roster: list[tuple[int, int, str]] = []
    names_seen: set[str] = set()
    student_ids_seen: set[int] = set()
    for position, item in enumerate(roster):
        if not isinstance(item, Mapping):
            raise ValueError("structured feedback roster item is invalid")
        student_id = item.get("student_id")
        student_name = _normalize_match_text(item.get("student_name"))
        if type(student_id) is not int or student_id <= 0 or student_id in student_ids_seen:
            raise ValueError("structured feedback roster item is invalid")
        if not student_name:
            raise ValueError("structured feedback roster name is invalid")
        if student_name in names_seen:
            raise ClassCommentaryStudentScopeError("student_roster_name_ambiguous")
        student_ids_seen.add(student_id)
        names_seen.add(student_name)
        normalized_roster.append((position, student_id, student_name))
    return normalized_roster


def match_class_commentary_eligible_student_ids(
    *,
    transcript_text: object,
    roster: object,
) -> list[int]:
    normalized_roster = _normalize_class_commentary_scope_roster(roster)

    transcript = _normalize_match_text(transcript_text)
    accepted_ids = {
        student_id
        for _, _, student_id in _match_normalized_student_name_spans(
            transcript,
            normalized_roster,
        )
    }

    eligible_ids = [
        student_id
        for _, student_id, _ in normalized_roster
        if student_id in accepted_ids
    ]
    if not eligible_ids:
        raise ClassCommentaryStudentScopeError("student_feedback_no_eligible_students")
    return eligible_ids


def resolve_class_commentary_attending_roster_student_ids(
    *,
    roster: object,
) -> list[int]:
    normalized_roster = _normalize_class_commentary_scope_roster(roster)
    eligible_ids = [student_id for _, student_id, _ in normalized_roster]
    if not eligible_ids:
        raise ClassCommentaryStudentScopeError("student_feedback_no_eligible_students")
    return eligible_ids


def build_class_commentary_eligible_scope_hash(
    *,
    transcript_hash: str,
    roster_hash: str,
    eligible_student_ids: list[int],
    matcher_version: str = CLASS_COMMENTARY_STUDENT_NAME_MATCHER_V1,
) -> str:
    envelope = {
        "attending_roster_hash": str(roster_hash or ""),
        "confirmed_transcript_hash": str(transcript_hash or ""),
        "eligible_student_ids": eligible_student_ids,
        "student_mention_matcher_version": str(matcher_version or ""),
    }
    return _content_hash(_canonical_json(envelope))


def _parse_frozen_scope(generation: Mapping[str, object]) -> tuple[list[int], dict[int, str]]:
    roster = _parse_json(generation.get("attending_roster_snapshot_json"))
    eligible_ids = _parse_json(generation.get("eligible_student_ids_json"))
    if not isinstance(roster, list) or not isinstance(eligible_ids, list) or not eligible_ids:
        raise ValueError("structured feedback frozen scope is invalid")

    roster_order: list[int] = []
    names_by_id: dict[int, str] = {}
    for item in roster:
        if not isinstance(item, dict):
            raise ValueError("structured feedback frozen roster is invalid")
        student_id = item.get("student_id")
        student_name = item.get("student_name")
        if (
            type(student_id) is not int
            or student_id <= 0
            or not isinstance(student_name, str)
            or not student_name.strip()
            or student_id in names_by_id
        ):
            raise ValueError("structured feedback frozen roster is invalid")
        roster_order.append(student_id)
        names_by_id[student_id] = student_name

    parsed_eligible_ids: list[int] = []
    for student_id in eligible_ids:
        if (
            type(student_id) is not int
            or student_id <= 0
            or student_id in parsed_eligible_ids
            or student_id not in names_by_id
        ):
            raise ValueError("structured feedback eligible scope is invalid")
        parsed_eligible_ids.append(student_id)
    if [student_id for student_id in roster_order if student_id in parsed_eligible_ids] != parsed_eligible_ids:
        raise ValueError("structured feedback eligible scope order is invalid")
    return parsed_eligible_ids, names_by_id


def validate_class_commentary_structured_generation_contract(
    generation: Mapping[str, object],
) -> None:
    if str(generation.get("feedback_schema_version") or "") != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1:
        raise ValueError("structured feedback schema contract is invalid")
    snapshot_hash_fields = (
        ("confirmed_transcript_snapshot", "confirmed_transcript_hash"),
        ("attending_roster_snapshot_json", "attending_roster_hash"),
        ("skill_content_snapshot", "skill_content_hash"),
    )
    if any(
        _content_hash(str(generation.get(snapshot_field) or ""))
        != str(generation.get(hash_field) or "")
        for snapshot_field, hash_field in snapshot_hash_fields
    ):
        raise ValueError("structured feedback core snapshot hash is invalid")
    eligible_ids, names_by_id = _parse_frozen_scope(generation)
    matcher_version = str(generation.get("student_mention_matcher_version") or "")
    prompt_version = str(generation.get("prompt_version") or "")
    contract_pair = (matcher_version, prompt_version)
    if contract_pair == (
        CLASS_COMMENTARY_STUDENT_NAME_MATCHER_V1,
        CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION,
    ):
        pass
    elif contract_pair == (
        CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1,
        CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
    ):
        if eligible_ids != list(names_by_id):
            raise ValueError("structured feedback attending roster scope is invalid")
        if not bool(generation.get("attending_roster_explicit")):
            raise ValueError("structured feedback attending roster scope must be explicit")
    else:
        raise ValueError("structured feedback prompt and scope contract is invalid")
    response_format = _parse_json(generation.get("response_format_json"))
    if response_format != CLASS_COMMENTARY_STRUCTURED_RESPONSE_FORMAT:
        raise ValueError("structured feedback response format contract is invalid")
    if (
        str(generation.get("student_history_memory_mode") or "")
        != CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_DISABLED_V1
    ):
        raise ValueError("structured feedback memory contract is invalid")
    expected_scope_hash = build_class_commentary_eligible_scope_hash(
        transcript_hash=str(generation.get("confirmed_transcript_hash") or ""),
        roster_hash=str(generation.get("attending_roster_hash") or ""),
        eligible_student_ids=eligible_ids,
        matcher_version=matcher_version,
    )
    if str(generation.get("eligible_student_scope_hash") or "") != expected_scope_hash:
        raise ValueError("structured feedback eligible scope hash is invalid")


def _only_student_name_and_punctuation(text: str, student_name: str) -> bool:
    normalized_text = _normalize_match_text(text)
    normalized_name = _normalize_match_text(student_name)
    if normalized_name:
        normalized_text = normalized_text.replace(normalized_name, "")
    return not any(
        not char.isspace()
        and not unicodedata.category(char).startswith("P")
        and not unicodedata.category(char).startswith("S")
        for char in normalized_text
    )


def canonicalize_class_commentary_structured_feedback(
    *,
    structured_feedback: object,
    generation: Mapping[str, object],
    validate_generation_contract: bool = True,
) -> dict:
    if validate_generation_contract:
        validate_class_commentary_structured_generation_contract(generation)
    try:
        parsed = _parse_json(structured_feedback)
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response is not valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response is not a JSON object",
        )
    if parsed.get("schema_version") != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "feedback_schema_mismatch",
            reason="response schema version does not match generation",
        )
    try:
        envelope = _StudentFeedbackEnvelopeV1.model_validate(parsed)
    except ValidationError as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response does not match the structured feedback schema",
        ) from exc

    eligible_ids, names_by_id = _parse_frozen_scope(generation)
    eligible_id_set = set(eligible_ids)
    normalized_roster = [
        (position, student_id, _normalize_match_text(student_name))
        for position, (student_id, student_name) in enumerate(names_by_id.items())
    ]
    items_by_id: dict[int, str] = {}
    for item in envelope.items:
        student_id = int(item.student_id)
        if student_id <= 0 or student_id not in names_by_id or student_id not in eligible_id_set:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_unknown_student",
                student_id=student_id if student_id > 0 else None,
                field="student_id",
            )
        if student_id in items_by_id:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_duplicate_student",
                student_id=student_id,
                field="student_id",
            )
        normalized_text = normalize_class_commentary_feedback_text(item.feedback_text)
        if not normalized_text or _only_student_name_and_punctuation(
            normalized_text,
            names_by_id[student_id],
        ):
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_empty",
                student_id=student_id,
                field="feedback_text",
            )
        if len(normalized_text) > CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_too_long",
                student_id=student_id,
                field="feedback_text",
                limit=CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT,
            )
        normalized_match_text = _normalize_match_text(normalized_text)
        matched_student_ids = {
            matched_student_id
            for _, _, matched_student_id in _match_normalized_student_name_spans(
                normalized_match_text,
                normalized_roster,
            )
        }
        if any(matched_student_id != student_id for matched_student_id in matched_student_ids):
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_cross_student_reference",
                student_id=student_id,
                field="feedback_text",
            )
        items_by_id[student_id] = normalized_text

    if set(items_by_id) != eligible_id_set:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_coverage_mismatch"
        )
    canonical_items = [
        {"student_id": student_id, "feedback_text": items_by_id[student_id]}
        for student_id in eligible_ids
    ]
    canonical_envelope = {
        "schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "items": canonical_items,
    }
    try:
        canonical_json = _canonical_json(canonical_envelope)
        canonical_hash = _content_hash(canonical_json)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response cannot be canonicalized",
        ) from exc
    response_items = [
        {
            "student_id": item["student_id"],
            "student_name": names_by_id[item["student_id"]],
            "feedback_text": item["feedback_text"],
        }
        for item in canonical_items
    ]
    derived_text = "\n\n".join(
        f"{item['student_name']}:\n{item['feedback_text']}"
        for item in response_items
    )
    if len(derived_text) > CLASS_COMMENTARY_STUDENT_FEEDBACK_TOTAL_LIMIT:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_too_long",
            field="feedback_text",
            limit=CLASS_COMMENTARY_STUDENT_FEEDBACK_TOTAL_LIMIT,
        )
    return {
        "feedback_schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "structured_feedback_json": canonical_json,
        "structured_feedback_hash": canonical_hash,
        "derived_feedback_text": derived_text,
        "student_feedback_items": response_items,
    }


def canonicalize_class_commentary_structured_feedback_replay(
    *,
    structured_feedback: object,
    frozen_structured_feedback: object,
) -> dict:
    try:
        frozen_parsed = _parse_json(frozen_structured_feedback)
        frozen_envelope = _StudentFeedbackEnvelopeV1.model_validate(frozen_parsed)
        parsed = _parse_json(structured_feedback)
        envelope = _StudentFeedbackEnvelopeV1.model_validate(parsed)
    except (TypeError, json.JSONDecodeError, ValidationError, RecursionError) as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="response does not match the frozen structured feedback schema",
        ) from exc

    frozen_student_ids: list[int] = []
    for item in frozen_envelope.items:
        student_id = int(item.student_id)
        if student_id <= 0 or student_id in frozen_student_ids:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "structured_feedback_invalid",
                reason="frozen structured feedback scope is invalid",
            )
        frozen_student_ids.append(student_id)
    if not frozen_student_ids:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            reason="frozen structured feedback scope is empty",
        )

    frozen_student_id_set = set(frozen_student_ids)
    items_by_id: dict[int, str] = {}
    for item in envelope.items:
        student_id = int(item.student_id)
        if student_id <= 0 or student_id not in frozen_student_id_set:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_unknown_student",
                student_id=student_id if student_id > 0 else None,
                field="student_id",
            )
        if student_id in items_by_id:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_duplicate_student",
                student_id=student_id,
                field="student_id",
            )
        normalized_text = normalize_class_commentary_feedback_text(item.feedback_text)
        if not normalized_text:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_empty",
                student_id=student_id,
                field="feedback_text",
            )
        if len(normalized_text) > CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_too_long",
                student_id=student_id,
                field="feedback_text",
                limit=CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT,
            )
        items_by_id[student_id] = normalized_text

    if set(items_by_id) != frozen_student_id_set:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_coverage_mismatch"
        )
    canonical_envelope = {
        "schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "items": [
            {
                "student_id": student_id,
                "feedback_text": items_by_id[student_id],
            }
            for student_id in frozen_student_ids
        ],
    }
    canonical_json = _canonical_json(canonical_envelope)
    return {
        "feedback_schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "structured_feedback_json": canonical_json,
        "structured_feedback_hash": _content_hash(canonical_json),
    }


def _validate_v1_feedback(
    *,
    structured_json: object,
    stored_hash: str,
    derived_text: str,
    generation: Mapping[str, object],
) -> list[dict]:
    canonical = canonicalize_class_commentary_structured_feedback(
        structured_feedback=structured_json,
        generation=generation,
    )
    if (
        str(structured_json or "") != canonical["structured_feedback_json"]
        or stored_hash != canonical["structured_feedback_hash"]
    ):
        raise ValueError("structured feedback integrity check failed")
    if derived_text != canonical["derived_feedback_text"]:
        raise ValueError("structured feedback derived text is invalid")
    return canonical["student_feedback_items"]


def build_class_commentary_feedback_read_envelope(
    *,
    schema_version: object,
    structured_json: object,
    stored_hash: object,
    derived_text: object,
    generation: Mapping[str, object] | None,
    allow_empty_generation_payload: bool = False,
) -> dict:
    normalized_schema_version = str(schema_version or "")
    normalized_hash = str(stored_hash or "")
    normalized_derived_text = str(derived_text or "")
    if not normalized_schema_version:
        return {
            "feedback_schema_version": "",
            "feedback_schema_status": "plain_text",
            "student_feedback_items": [],
            "structured_feedback_hash": "",
            "derived_feedback_text": normalized_derived_text,
            "writable": True,
        }
    if normalized_schema_version != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1:
        return {
            "feedback_schema_version": normalized_schema_version,
            "feedback_schema_status": "unsupported",
            "student_feedback_items": [],
            "structured_feedback_hash": normalized_hash,
            "derived_feedback_text": normalized_derived_text,
            "writable": False,
        }
    if generation is None:
        return _invalid_envelope(
            schema_version=normalized_schema_version,
            stored_hash=normalized_hash,
            derived_text=normalized_derived_text,
        )
    if allow_empty_generation_payload and str(generation.get("status") or "") in {
        "generating",
        "failed",
    }:
        payload_is_empty = (
            str(structured_json or "") == ""
            and normalized_hash == ""
            and normalized_derived_text == ""
        )
        try:
            if not payload_is_empty:
                raise ValueError("nonterminal structured generation has result data")
            validate_class_commentary_structured_generation_contract(generation)
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
            return _invalid_envelope(
                schema_version=normalized_schema_version,
                stored_hash=normalized_hash,
                derived_text=normalized_derived_text,
            )
        return {
            "feedback_schema_version": normalized_schema_version,
            "feedback_schema_status": "supported",
            "student_feedback_items": [],
            "structured_feedback_hash": "",
            "derived_feedback_text": "",
            "writable": False,
        }
    try:
        response_items = _validate_v1_feedback(
            structured_json=structured_json,
            stored_hash=normalized_hash,
            derived_text=normalized_derived_text,
            generation=generation,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return _invalid_envelope(
            schema_version=normalized_schema_version,
            stored_hash=normalized_hash,
            derived_text=normalized_derived_text,
        )
    return {
        "feedback_schema_version": normalized_schema_version,
        "feedback_schema_status": "supported",
        "student_feedback_items": response_items,
        "structured_feedback_hash": normalized_hash,
        "derived_feedback_text": normalized_derived_text,
        "writable": True,
    }
