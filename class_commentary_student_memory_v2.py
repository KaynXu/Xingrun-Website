from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping

from class_commentary import (
    CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
    CLASS_COMMENTARY_TEMPERATURE,
    normalize_class_commentary_feedback_text,
)
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
    CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT,
    CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
    ClassCommentaryStructuredFeedbackValidationError,
)


CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V3 = (
    "class_commentary.student_evidence_segment.v3"
)


class ClassCommentaryStudentEvidenceAttributionError(ValueError):
    code = "student_evidence_attribution_failed"


ISOLATED_STUDENT_SYSTEM_PROMPT = (
    "Generate feedback for exactly one CURRENT_STUDENT. "
    "CURRENT_STUDENT_EVIDENCE contains verified excerpts from this lesson. "
    "STUDENT_HISTORY_MEMORIES is historical context only and must never be described "
    "as something newly observed in this lesson. STUDENT_LEARNING_GRAPH contains only "
    "server-validated history for this same student and subject. Cite graph history only "
    "through used_graph_evidence_refs from the supplied allowlist. "
    "Current evidence and the confirmed "
    "attendance scope override history whenever they differ. TEACHER_STYLE_MEMORIES may "
    "change expression and focus only. Never infer, mention, or output another student. "
    "Return only the requested JSON object."
)

CLASS_COMMENTARY_STUDENT_RUN_SCHEMA_V1 = (
    "class_commentary.student_generation_run.v1"
)

ISOLATED_STUDENT_OUTPUT_RULES = (
    "Return a JSON object with schema_version, items, and used_graph_evidence_refs.",
    "Set schema_version to class_commentary.student_feedback.v1.",
    "Return exactly one item with exactly student_id and feedback_text.",
    "Set used_graph_evidence_refs to only evidence_ref values actually used from STUDENT_LEARNING_GRAPH; otherwise return an empty array.",
    "Use only CURRENT_STUDENT.student_id as student_id.",
    "Write as the teacher speaking directly to CURRENT_STUDENT.",
    "Do not output any student name; the server supplies display names.",
    "Use CURRENT_STUDENT_EVIDENCE as this lesson's only student-specific evidence.",
    "Treat STUDENT_HISTORY_MEMORIES only as historical context, never as a new observation from this lesson.",
    "When current evidence conflicts with history, follow current evidence.",
    "Do not mention or infer another student's identity, evidence, memory, or facts.",
    "If current student evidence is empty, do not invent an individual observation.",
)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def canonical_hash(value: object) -> str:
    return content_hash(canonical_json(value))


def _normalized_name(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def _roster_entries(roster: Iterable[Mapping[str, object]]) -> list[dict]:
    entries = []
    names = set()
    student_ids = set()
    for item in roster:
        student_id = int(item.get("student_id") or item.get("id") or 0)
        name = _normalized_name(item.get("student_name") or item.get("name"))
        if student_id <= 0 or not name or student_id in student_ids or name in names:
            raise ValueError("student evidence roster is invalid or ambiguous")
        student_ids.add(student_id)
        names.add(name)
        entries.append({"student_id": student_id, "name": name})
    return entries


_CLAUSE_PATTERN = re.compile(r"[^\n\r。！？!?；;.,，]+[\n\r。！？!?；;.,，]*")
_STUDENT_ID_PATTERN = re.compile(
    r"(?:student[_\s-]*id|学生\s*(?:id|ID|编号)|学员\s*(?:id|ID|编号))"
    r"\s*[:：=#-]?\s*([0-9]+)",
    flags=re.IGNORECASE,
)


def _evidence_fragment(transcript: str, start: int, end: int) -> dict | None:
    raw = transcript[start:end]
    left = len(raw) - len(raw.lstrip())
    right = len(raw.rstrip())
    fragment_start = start + left
    fragment_end = start + right
    text = transcript[fragment_start:fragment_end]
    if not text:
        return None
    return {
        "start": fragment_start,
        "end": fragment_end,
        "text": text,
        "text_hash": content_hash(text),
    }


def _unmatched_roster_aliases(clause: str, roster: list[dict]) -> set[int]:
    aliases = set()
    for item in roster:
        official_name = str(item["name"])
        if official_name in clause:
            continue
        core_name = re.sub(r"^(?:学生|学员)|(?:同学)$", "", official_name).strip()
        if not core_name:
            continue
        guarded_aliases = {f"{core_name}同学", f"小{core_name}"}
        if any(alias in clause for alias in guarded_aliases):
            aliases.add(int(item["student_id"]))
    return aliases


def build_student_evidence_assignment(
    *,
    transcript: str,
    transcript_hash: str,
    roster: Iterable[Mapping[str, object]],
    attending_student_ids: Iterable[int],
    matcher_version: str = CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V3,
) -> dict:
    frozen_transcript = str(transcript or "")
    if content_hash(frozen_transcript) != str(transcript_hash or ""):
        raise ValueError("confirmed transcript hash mismatch")
    if matcher_version != CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V3:
        raise ValueError("student evidence matcher version is unsupported")
    normalized_roster = _roster_entries(roster)
    roster_ids = {item["student_id"] for item in normalized_roster}
    attending_ids = [int(value) for value in attending_student_ids]
    if (
        not attending_ids
        or len(set(attending_ids)) != len(attending_ids)
        or any(student_id not in roster_ids for student_id in attending_ids)
    ):
        raise ValueError("attending students are outside the frozen roster")

    assignments: dict[int, list[dict]] = {student_id: [] for student_id in attending_ids}
    carried_owner_id: int | None = None
    for clause_match in _CLAUSE_PATTERN.finditer(frozen_transcript):
        clause = clause_match.group(0)
        normalized_clause = _normalized_name(clause)
        named_ids = {
            item["student_id"]
            for item in normalized_roster
            if item["name"] in normalized_clause
        }
        referenced_ids = {
            int(match.group(1)) for match in _STUDENT_ID_PATTERN.finditer(normalized_clause)
        }
        unmatched_alias_ids = _unmatched_roster_aliases(
            normalized_clause, normalized_roster
        )
        if unmatched_alias_ids:
            raise ClassCommentaryStudentEvidenceAttributionError(
                "student evidence clause contains an unverified alias"
            )
        owner_ids = named_ids | referenced_ids
        if not owner_ids:
            if carried_owner_id is not None:
                fragment = _evidence_fragment(
                    frozen_transcript, clause_match.start(), clause_match.end()
                )
                if fragment is not None:
                    assignments[carried_owner_id].append(fragment)
            carried_owner_id = (
                carried_owner_id
                if normalized_clause.rstrip().endswith((",", "，"))
                else None
            )
            continue
        if (
            len(owner_ids) != 1
            or not owner_ids.issubset(roster_ids)
            or not owner_ids.issubset(set(attending_ids))
        ):
            raise ClassCommentaryStudentEvidenceAttributionError(
                "student evidence clause is not uniquely attributable"
            )
        owner_id = next(iter(owner_ids))
        carried_owner_id = (
            owner_id if normalized_clause.rstrip().endswith((",", "，")) else None
        )
        fragment = _evidence_fragment(
            frozen_transcript, clause_match.start(), clause_match.end()
        )
        if fragment is not None:
            assignments[owner_id].append(fragment)
    if any(not assignments[student_id] for student_id in attending_ids):
        raise ClassCommentaryStudentEvidenceAttributionError(
            "student evidence attribution is incomplete"
        )
    assignment = {
        "schema_version": "class_commentary.student_evidence_assignment.v1",
        "matcher_version": matcher_version,
        "transcript_hash": str(transcript_hash),
        "roster_student_ids": [item["student_id"] for item in normalized_roster],
        "attending_student_ids": attending_ids,
        "fragments_by_student_id": {
            str(student_id): assignments[student_id] for student_id in attending_ids
        },
    }
    return {**assignment, "assignment_hash": canonical_hash(assignment)}


def build_student_current_evidence(
    *,
    transcript: str,
    transcript_hash: str,
    roster: Iterable[Mapping[str, object]],
    target_student_id: int,
    matcher_version: str = CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
    assignment: Mapping[str, object] | None = None,
) -> dict:
    frozen_transcript = str(transcript or "")
    if content_hash(frozen_transcript) != str(transcript_hash or ""):
        raise ValueError("confirmed transcript hash mismatch")
    if matcher_version not in {
        CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2,
        CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V3,
    }:
        raise ValueError("student evidence matcher version is unsupported")
    normalized_roster = _roster_entries(roster)
    target_ids = {item["student_id"] for item in normalized_roster}
    if int(target_student_id) not in target_ids:
        raise ValueError("target student is outside the frozen roster")
    if matcher_version == CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V2:
        if assignment is not None:
            raise ValueError("legacy student evidence does not accept an assignment")
        attribution = "fail_closed_no_structured_ownership"
        fragments = []
    else:
        if not isinstance(assignment, Mapping):
            raise ValueError("student evidence assignment is required")
        assignment_payload = {
            key: value for key, value in assignment.items() if key != "assignment_hash"
        }
        fragments_by_student = assignment.get("fragments_by_student_id")
        assignment_roster_ids = assignment.get("roster_student_ids")
        assignment_attending_ids = assignment.get("attending_student_ids")
        if (
            canonical_hash(assignment_payload)
            != str(assignment.get("assignment_hash") or "")
            or assignment.get("schema_version")
            != "class_commentary.student_evidence_assignment.v1"
            or assignment.get("matcher_version") != matcher_version
            or assignment.get("transcript_hash") != str(transcript_hash)
            or assignment_roster_ids
            != [item["student_id"] for item in normalized_roster]
            or not isinstance(assignment_attending_ids, list)
            or int(target_student_id) not in assignment_attending_ids
            or set(assignment_attending_ids) - target_ids
            or not isinstance(fragments_by_student, Mapping)
            or set(fragments_by_student)
            != {str(student_id) for student_id in assignment_attending_ids}
        ):
            raise ValueError("student evidence assignment is invalid")
        fragments = fragments_by_student.get(str(int(target_student_id)))
        if not isinstance(fragments, list) or not fragments:
            raise ClassCommentaryStudentEvidenceAttributionError(
                "student evidence is missing"
            )
        for fragment in fragments:
            if not isinstance(fragment, Mapping) or set(fragment) != {
                "start", "end", "text", "text_hash"
            }:
                raise ValueError("student evidence fragment is invalid")
            start = fragment.get("start")
            end = fragment.get("end")
            text = str(fragment.get("text") or "")
            if (
                type(start) is not int
                or type(end) is not int
                or start < 0
                or end <= start
                or frozen_transcript[start:end] != text
                or content_hash(text) != str(fragment.get("text_hash") or "")
            ):
                raise ValueError("student evidence fragment provenance mismatch")
        attribution = "unique_clause_owner_v3"
    snapshot = {
        "schema_version": "class_commentary.student_current_evidence.v1",
        "matcher_version": matcher_version,
        "transcript_hash": str(transcript_hash),
        "attribution": attribution,
        "fragments": [dict(fragment) for fragment in fragments],
    }
    return {**snapshot, "snapshot_hash": canonical_hash(snapshot)}


def build_safe_class_context(*, class_record: Mapping[str, object], subject_key: str) -> dict:
    return {
        "subject_key": str(subject_key or "").strip(),
    }


def build_student_memory_query(
    *,
    evidence_snapshot: Mapping[str, object],
    class_context: Mapping[str, object],
) -> str:
    fragments = evidence_snapshot.get("fragments")
    evidence_text = "\n".join(
        str(item.get("text") or "").strip()
        for item in (fragments if isinstance(fragments, list) else [])
        if isinstance(item, Mapping) and str(item.get("text") or "").strip()
    )
    parts = [
        f"subject:{str(class_context.get('subject_key') or '').strip()}",
    ]
    if evidence_text:
        parts.append("current_evidence:\n" + evidence_text)
    return "\n".join(parts)[:2000]


def _prompt_memory_items(items: object, *, historical: bool) -> list[dict]:
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, Mapping):
            continue
        memory_text = str(item.get("memory_text") or "").strip()
        if not memory_text:
            continue
        if historical:
            result.append(
                {
                    "historical_context": memory_text,
                    "source_time": str(item.get("created_at") or ""),
                }
            )
        else:
            result.append({"style_rule": memory_text})
    return result


def build_isolated_student_chat_request(
    *,
    student_id: int,
    student_name: str,
    class_context: Mapping[str, object],
    evidence_snapshot: Mapping[str, object],
    student_history_memories: object,
    teacher_style_memories: object,
    skill_content: str,
    model_parameters: Mapping[str, object],
    graph_context: object = None,
) -> dict:
    evidence_for_prompt = {
        "verified_fragments": [
            {
                "start": item.get("start"),
                "end": item.get("end"),
                "text": str(item.get("text") or ""),
                "text_hash": str(item.get("text_hash") or ""),
            }
            for item in evidence_snapshot.get("fragments") or []
            if isinstance(item, Mapping) and str(item.get("text") or "").strip()
        ],
    }
    style_rules = _prompt_memory_items(teacher_style_memories, historical=False)
    if str(skill_content or "").strip():
        style_rules.insert(
            0,
            {
                "style_rule": str(skill_content).strip(),
                "source": "frozen_active_skill",
            },
        )
    sections = (
        "[CURRENT_STUDENT]\n"
        + canonical_json(
            {"student_id": int(student_id), "display_name": str(student_name or "")}
        ),
        "[CURRENT_CLASS_CONTEXT]\n" + canonical_json(dict(class_context)),
        "[CURRENT_STUDENT_EVIDENCE]\n" + canonical_json(evidence_for_prompt),
        "[STUDENT_HISTORY_MEMORIES]\n"
        + canonical_json(
            _prompt_memory_items(student_history_memories, historical=True)
        ),
        "[STUDENT_LEARNING_GRAPH]\n"
        + canonical_json(
            dict(graph_context) if isinstance(graph_context, Mapping) else {}
        ),
        "[TEACHER_STYLE_MEMORIES]\n"
        + canonical_json(style_rules),
        "[OUTPUT_RULES]\n"
        + "\n".join(f"- {rule}" for rule in ISOLATED_STUDENT_OUTPUT_RULES),
    )
    return {
        "prompt_version": CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
        "messages": [
            {"role": "system", "content": ISOLATED_STUDENT_SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(sections)},
        ],
        "temperature": float(
            model_parameters.get("temperature", CLASS_COMMENTARY_TEMPERATURE)
        ),
        "response_format": {"type": "json_object"},
        "student_history_memory_mode": (
            CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
        ),
    }


def _contains_student_id_field(text: str, student_id: int) -> bool:
    return bool(
        re.search(
            rf'"student_id":{re.escape(str(int(student_id)))}(?![0-9])',
            text,
        )
    )


def _contains_student_id_reference(text: str, student_id: int) -> bool:
    return bool(
        re.search(
            rf"(?:student[_\s-]*id|学生\s*(?:id|ID|编号)|学员\s*(?:id|ID|编号))"
            rf"\s*[:：=#-]?\s*{re.escape(str(int(student_id)))}(?![0-9])",
            text,
            flags=re.IGNORECASE,
        )
    )


def validate_isolated_prompt_privacy(
    *,
    chat_request: Mapping[str, object],
    target_student_id: int,
    target_student_name: str,
    other_students: Iterable[Mapping[str, object]],
    forbidden_private_values: Iterable[object] = (),
) -> None:
    serialized = canonical_json(chat_request)
    messages = chat_request.get("messages")
    visible_prompt = "\n".join(
        str(message.get("content") or "")
        for message in (messages if isinstance(messages, list) else [])
        if isinstance(message, Mapping)
    )
    for item in other_students:
        other_id = int(item.get("student_id") or item.get("id") or 0)
        other_name = str(item.get("student_name") or item.get("name") or "").strip()
        if (
            other_id > 0
            and other_id != int(target_student_id)
            and (
                _contains_student_id_field(visible_prompt, other_id)
                or _contains_student_id_reference(visible_prompt, other_id)
            )
        ):
            raise ValueError("isolated prompt contains another student_id")
        if other_name and other_name != str(target_student_name) and other_name in serialized:
            raise ValueError("isolated prompt contains another student name")
    for value in forbidden_private_values:
        normalized = str(value or "").strip()
        if normalized and normalized in serialized:
            raise ValueError("isolated prompt contains another student's private value")


def validate_single_student_response(
    *,
    response: object,
    target_student_id: int,
    target_student_name: str,
    other_students: Iterable[Mapping[str, object]],
    forbidden_private_values: Iterable[object] = (),
) -> dict:
    try:
        payload = response if isinstance(response, dict) else json.loads(str(response or ""))
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid",
            student_id=int(target_student_id),
            reason="student response is not valid JSON",
        ) from exc
    allowed_top_level = {"schema_version", "items"}
    if isinstance(payload, dict) and "used_graph_evidence_refs" in payload:
        allowed_top_level.add("used_graph_evidence_refs")
    if not isinstance(payload, dict) or set(payload) != allowed_top_level:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid", student_id=int(target_student_id)
        )
    items = payload.get("items")
    if payload.get("schema_version") != CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1 or not isinstance(items, list) or len(items) != 1:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_coverage_mismatch", student_id=int(target_student_id)
        )
    item = items[0]
    if not isinstance(item, dict) or set(item) != {"student_id", "feedback_text"}:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid", student_id=int(target_student_id)
        )
    if type(item.get("student_id")) is not int or item["student_id"] != int(target_student_id):
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_unknown_student", student_id=int(target_student_id)
        )
    feedback_text = normalize_class_commentary_feedback_text(item.get("feedback_text"))
    if not feedback_text:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_empty", student_id=int(target_student_id)
        )
    if len(feedback_text) > CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT:
        raise ClassCommentaryStructuredFeedbackValidationError(
            "student_feedback_too_long",
            student_id=int(target_student_id),
            limit=CLASS_COMMENTARY_STUDENT_FEEDBACK_ITEM_LIMIT,
        )
    all_students = [
        {
            "student_id": int(target_student_id),
            "student_name": str(target_student_name or ""),
        },
        *list(other_students),
    ]
    for other in all_students:
        other_id = int(other.get("student_id") or other.get("id") or 0)
        other_name = str(other.get("student_name") or other.get("name") or "").strip()
        if other_id > 0 and other_id != int(target_student_id) and _contains_student_id_reference(
            feedback_text, other_id
        ):
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_cross_student_reference",
                student_id=int(target_student_id),
            )
        if other_name and other_name in feedback_text:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_cross_student_reference",
                student_id=int(target_student_id),
            )
    for value in forbidden_private_values:
        normalized = str(value or "").strip()
        if normalized and normalized in feedback_text:
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_cross_student_reference",
                student_id=int(target_student_id),
            )
    canonical = {
        "schema_version": CLASS_COMMENTARY_STUDENT_FEEDBACK_SCHEMA_V1,
        "items": [{"student_id": int(target_student_id), "feedback_text": feedback_text}],
    }
    canonical_text = canonical_json(canonical)
    used_graph_evidence_refs = payload.get("used_graph_evidence_refs", [])
    if not isinstance(used_graph_evidence_refs, list) or any(
        not isinstance(value, str) or not value for value in used_graph_evidence_refs
    ):
        raise ClassCommentaryStructuredFeedbackValidationError(
            "structured_feedback_invalid", student_id=int(target_student_id)
        )
    return {
        "student_id": int(target_student_id),
        "feedback_text": feedback_text,
        "structured_feedback_json": canonical_text,
        "structured_feedback_hash": content_hash(canonical_text),
        "used_graph_evidence_refs": list(dict.fromkeys(used_graph_evidence_refs)),
    }
