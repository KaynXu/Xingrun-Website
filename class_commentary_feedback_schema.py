from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from class_commentary import normalize_class_commentary_feedback_text


CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1 = "class_commentary.student_feedback.v1"


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


def _validate_v1_feedback(
    *,
    structured_json: object,
    stored_hash: str,
    derived_text: str,
    generation: Mapping[str, object],
) -> list[dict]:
    parsed = _parse_json(structured_json)
    if not isinstance(parsed, dict) or set(parsed) != {"schema_version", "items"}:
        raise ValueError("structured feedback envelope is invalid")
    if parsed.get("schema_version") != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1:
        raise ValueError("structured feedback schema version is invalid")
    raw_items = parsed.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("structured feedback items are invalid")

    eligible_ids, names_by_id = _parse_frozen_scope(generation)
    items_by_id: dict[int, str] = {}
    for item in raw_items:
        if not isinstance(item, dict) or set(item) != {"student_id", "feedback_text"}:
            raise ValueError("structured feedback item is invalid")
        student_id = item.get("student_id")
        feedback_text = item.get("feedback_text")
        if (
            type(student_id) is not int
            or student_id <= 0
            or student_id in items_by_id
            or not isinstance(feedback_text, str)
        ):
            raise ValueError("structured feedback item is invalid")
        normalized_text = normalize_class_commentary_feedback_text(feedback_text)
        if not normalized_text or normalized_text != feedback_text or len(normalized_text) > 2000:
            raise ValueError("structured feedback text is invalid")
        items_by_id[student_id] = normalized_text
    if set(items_by_id) != set(eligible_ids):
        raise ValueError("structured feedback coverage is invalid")

    canonical_items = [
        {"student_id": student_id, "feedback_text": items_by_id[student_id]}
        for student_id in eligible_ids
    ]
    canonical_json = _canonical_json({
        "schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "items": canonical_items,
    })
    if str(structured_json or "") != canonical_json or stored_hash != _content_hash(canonical_json):
        raise ValueError("structured feedback integrity check failed")

    response_items = [
        {
            "student_id": item["student_id"],
            "student_name": names_by_id[item["student_id"]],
            "feedback_text": item["feedback_text"],
        }
        for item in canonical_items
    ]
    expected_derived_text = "\n\n".join(
        f"{item['student_name']}:\n{item['feedback_text']}"
        for item in response_items
    )
    if len(expected_derived_text) > 30000 or derived_text != expected_derived_text:
        raise ValueError("structured feedback derived text is invalid")
    return response_items


def build_class_commentary_feedback_read_envelope(
    *,
    schema_version: object,
    structured_json: object,
    stored_hash: object,
    derived_text: object,
    generation: Mapping[str, object] | None,
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
