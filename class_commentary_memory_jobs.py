from __future__ import annotations

import json
import logging
import os
import re
import socket
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Mapping, Optional

import ai_processor
import config_runtime
from class_commentary_memory import ClassCommentaryMemoryService
from class_commentary_memory_privacy import (
    contains_class_commentary_private_information,
    contains_class_commentary_roster_name,
    normalize_class_commentary_roster_name,
)


_MAX_SUPPORT_ITEMS = 12
_MAX_SUPPORT_CHARS = 500

logger = logging.getLogger(__name__)


def _runtime_config(runtime_config: Optional[Mapping[str, object]] = None) -> dict:
    return dict(runtime_config if runtime_config is not None else config_runtime.get_runtime_config())


def _enabled(config: Mapping[str, object]) -> bool:
    return config_runtime.normalize_bool_flag(config.get("class_commentary_memory_enabled"))


def _store(store=None):
    if store is not None:
        return store
    import lesson_manager

    return lesson_manager


def _rq_context() -> tuple[str, Optional[str]]:
    rq_job_id = None
    try:
        from rq import get_current_job

        current_job = get_current_job()
        rq_job_id = str(current_job.id) if current_job is not None else None
    except Exception:
        rq_job_id = None
    owner = f"{socket.gethostname()}:{os.getpid()}"
    return owner, rq_job_id


def _default_extractor(extraction_input: dict, config: Mapping[str, object]):
    return ai_processor.extract_class_commentary_memory_signals(
        extraction_input=extraction_input,
        provider=str(config.get("class_commentary_provider") or config.get("provider") or ""),
        model=str(config.get("class_commentary_model") or ""),
        openai_api_key=str(
            config.get("class_commentary_openai_api_key") or config.get("openai_api_key") or ""
        ),
        openai_base_url=str(
            config.get("class_commentary_openai_base_url") or config.get("openai_base_url") or ""
        ),
        openai_headers=str(config.get("class_commentary_openai_headers") or ""),
        include_usage=True,
    )


def _json_value(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _frozen_roster(extraction_input: Mapping[str, object]) -> list[dict]:
    candidates = [
        extraction_input.get("attending_roster"),
        extraction_input.get("attending_roster_snapshot"),
    ]
    generation = extraction_input.get("generation")
    if isinstance(generation, Mapping):
        candidates.extend(
            [
                generation.get("attending_roster"),
                generation.get("attending_roster_snapshot"),
                generation.get("attending_roster_snapshot_json"),
            ]
        )
    for candidate in candidates:
        candidate = _json_value(candidate)
        if isinstance(candidate, list):
            return [dict(item) for item in candidate if isinstance(item, Mapping)]
    return []


def _normalize_name(value: object) -> str:
    return normalize_class_commentary_roster_name(value)


def _roster_names(roster: list[dict], *, student_id: Optional[int] = None) -> list[str]:
    names = []
    for item in roster:
        try:
            item_student_id = int(item.get("student_id"))
        except (TypeError, ValueError):
            continue
        if student_id is not None and item_student_id != student_id:
            continue
        name = str(item.get("student_name") or item.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _contains_name(value: object, name: str) -> bool:
    return bool(name) and _normalize_name(name) in _normalize_name(value)


def _replace_name(value: object, name: str) -> str:
    text = str(value or "")
    characters = [re.escape(character) for character in str(name or "").strip()]
    if not characters:
        return text
    return re.sub(r"\s*".join(characters), "该学生", text, flags=re.IGNORECASE)


def _resolve_student_id(signal: Mapping[str, object], roster: list[dict]) -> Optional[int]:
    by_id = {}
    by_name = {}
    for item in roster:
        try:
            student_id = int(item.get("student_id"))
        except (TypeError, ValueError):
            continue
        student_name = _normalize_name(item.get("student_name") or item.get("name"))
        by_id[student_id] = student_name
        if student_name:
            by_name.setdefault(student_name, []).append(student_id)

    hint = signal.get("student_id_hint")
    try:
        hinted_id = int(hint) if hint is not None else None
    except (TypeError, ValueError):
        hinted_id = None
    signal_name = _normalize_name(signal.get("student_name"))
    if hinted_id in by_id:
        if signal_name and by_id[hinted_id] != signal_name:
            return None
        return hinted_id
    name_matches = by_name.get(signal_name, []) if signal_name else []
    return name_matches[0] if len(name_matches) == 1 else None


def _normalize_extracted_items(payload: object, extraction_input: Mapping[str, object]) -> tuple[list[dict], int]:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    if not isinstance(payload, Mapping):
        raise ValueError("memory extractor returned an invalid payload")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("memory extractor items must be a list")
    roster = _frozen_roster(extraction_input)
    all_roster_names = _roster_names(roster)
    items = []
    dropped = 0
    for raw_item in raw_items:
        if hasattr(raw_item, "model_dump"):
            raw_item = raw_item.model_dump(mode="json")
        if not isinstance(raw_item, Mapping):
            dropped += 1
            continue
        memory_type = str(raw_item.get("memory_type") or "")
        if memory_type == "evaluation_only":
            dropped += 1
            continue
        if memory_type not in {"teacher_style", "student_fact"}:
            dropped += 1
            continue
        memory_text = str(raw_item.get("memory_text") or "").strip()
        raw_support = raw_item.get("support")
        if not memory_text or not isinstance(raw_support, (list, tuple)):
            dropped += 1
            continue
        support = [
            str(value or "").strip()[:_MAX_SUPPORT_CHARS]
            for value in raw_support[:_MAX_SUPPORT_ITEMS]
            if str(value or "").strip()
        ]
        if not support or any(
            contains_class_commentary_private_information(value)
            for value in [memory_text, *support]
        ):
            dropped += 1
            continue
        item = {
            "memory_type": memory_type,
            "memory_text": memory_text,
            "confidence": raw_item.get("confidence", 0.5),
            "evidence": {"support": support},
        }
        if memory_type == "teacher_style" and any(
            _contains_name(value, name)
            for value in [memory_text, *support]
            for name in all_roster_names
        ):
            dropped += 1
            continue
        if memory_type == "student_fact":
            student_id = _resolve_student_id(raw_item, roster)
            if student_id is None:
                dropped += 1
                continue
            target_names = _roster_names(roster, student_id=student_id)
            other_names = [name for name in all_roster_names if name not in target_names]
            if any(
                _contains_name(value, name)
                for value in [memory_text, *support]
                for name in other_names
            ):
                dropped += 1
                continue
            for name in target_names:
                item["memory_text"] = _replace_name(item["memory_text"], name)
                item["evidence"]["support"] = [
                    _replace_name(value, name) for value in item["evidence"]["support"]
                ]
            item["evidence"]["support"] = [
                value[:_MAX_SUPPORT_CHARS] for value in item["evidence"]["support"]
            ]
            item["student_id"] = student_id
        items.append(item)
    return items, dropped


def process_class_commentary_memory_extraction_job(
    job_id: int,
    *,
    store=None,
    extractor=None,
    dispatcher=None,
    runtime_config: Optional[Mapping[str, object]] = None,
    claim_owner: Optional[str] = None,
    rq_job_id: Optional[str] = None,
) -> dict:
    config = _runtime_config(runtime_config)
    if not _enabled(config):
        return {"enabled": False, "status": "disabled", "job_id": int(job_id)}

    target_store = _store(store)
    default_owner, current_rq_job_id = _rq_context()
    claimed = target_store.claim_class_commentary_memory_extraction_job(
        int(job_id),
        claim_owner=claim_owner or default_owner,
        rq_job_id=rq_job_id or current_rq_job_id,
    )
    if not claimed:
        return {"enabled": True, "status": "not_claimed", "job_id": int(job_id)}

    claim_token = str(claimed["claim_token"])
    try:
        frozen = target_store.get_class_commentary_memory_extraction_input(int(job_id))
        if not isinstance(frozen, Mapping):
            target_store.mark_class_commentary_memory_extraction_integrity_failed(
                int(job_id), claim_token=claim_token, error="immutable extraction input is missing"
            )
            return {"enabled": True, "status": "integrity_failed", "job_id": int(job_id)}
        if frozen.get("integrity_valid") is False:
            target_store.mark_class_commentary_memory_extraction_integrity_failed(
                int(job_id), claim_token=claim_token, error="immutable extraction input failed integrity"
            )
            return {"enabled": True, "status": "integrity_failed", "job_id": int(job_id)}
        if frozen.get("is_effective_revision") is False:
            result = target_store.commit_class_commentary_memory_extraction(
                int(job_id), claim_token=claim_token, items=[], result_summary={"obsolete": True}
            )
            return {"enabled": True, "status": result["job"]["status"], "job_id": int(job_id)}
        for hash_key in ("extraction_input_hash", "learning_evidence_hash"):
            if frozen.get(hash_key) is not None and str(frozen.get(hash_key)) != str(claimed.get(hash_key)):
                target_store.mark_class_commentary_memory_extraction_integrity_failed(
                    int(job_id), claim_token=claim_token, error=f"{hash_key}_mismatch"
                )
                return {"enabled": True, "status": "integrity_failed", "job_id": int(job_id)}

        extraction_input_value = frozen.get("extraction_input", frozen)
        if not isinstance(extraction_input_value, Mapping):
            target_store.mark_class_commentary_memory_extraction_integrity_failed(
                int(job_id), claim_token=claim_token, error="immutable extraction input payload is invalid"
            )
            return {"enabled": True, "status": "integrity_failed", "job_id": int(job_id)}
        extraction_input = dict(extraction_input_value)
        extract = extractor or _default_extractor
        extracted = extract(extraction_input, config)
        usage = {}
        if isinstance(extracted, tuple):
            extracted, usage = extracted
        items, dropped = _normalize_extracted_items(extracted, extraction_input)
        result = target_store.commit_class_commentary_memory_extraction(
            int(job_id),
            claim_token=claim_token,
            items=items,
            result_summary={
                "extracted_item_count": len(items),
                "dropped_item_count": dropped,
                "usage": usage if isinstance(usage, Mapping) else {},
            },
        )
    except Exception as exc:
        try:
            target_store.fail_class_commentary_memory_extraction_job(
                int(job_id), claim_token=claim_token, error=str(exc)
            )
        except Exception:
            pass
        raise

    if dispatcher is None:
        from class_commentary_memory_queue import dispatch_class_commentary_memory_work

        dispatcher = dispatch_class_commentary_memory_work
    try:
        dispatch_result = dispatcher(store=target_store, runtime_config=config)
    except Exception as exc:
        logger.warning(
            "class commentary memory dispatch failed after extraction job %s: %s",
            job_id,
            type(exc).__name__,
        )
        dispatch_result = {"queued": False, "error_type": exc.__class__.__name__}
    logger.info(
        "class commentary memory extraction job %s finished: status=%s operations=%d",
        job_id,
        result["job"]["status"],
        len(result.get("operations") or []),
    )
    return {
        "enabled": True,
        "status": str(result["job"]["status"]),
        "job_id": int(job_id),
        "operation_ids": [int(item["id"]) for item in result.get("operations", [])],
        "dispatch": dispatch_result,
    }


def _class_commentary_ai_kwargs(config: Mapping[str, object]) -> dict:
    return {
        "provider": str(
            config.get("class_commentary_provider") or config.get("provider") or ""
        ),
        "model": str(config.get("class_commentary_model") or ""),
        "openai_api_key": str(
            config.get("class_commentary_openai_api_key")
            or config.get("openai_api_key")
            or ""
        ),
        "openai_base_url": str(
            config.get("class_commentary_openai_base_url")
            or config.get("openai_base_url")
            or ""
        ),
        "openai_headers": str(config.get("class_commentary_openai_headers") or ""),
        "include_usage": True,
    }


def _candidate_style_rules(frozen: Mapping[str, object]) -> list[dict]:
    build = frozen.get("build")
    if not isinstance(build, Mapping):
        raise ValueError("candidate build input is missing")
    samples = frozen.get("revision_samples")
    evidence_items = frozen.get("style_evidence")
    if not isinstance(samples, list) or not isinstance(evidence_items, list):
        raise ValueError("candidate frozen sources are invalid")
    task_id_by_candidate_revision_id = {}
    for sample in samples:
        if not isinstance(sample, Mapping):
            raise ValueError("candidate revision sample is invalid")
        task_id_by_candidate_revision_id[int(sample["candidate_revision_id"])] = int(
            sample["task_id"]
        )
    grouped: dict[int, dict] = {}
    for evidence in evidence_items:
        if not isinstance(evidence, Mapping):
            raise ValueError("candidate style evidence is invalid")
        candidate_revision_id = int(evidence["candidate_revision_id"])
        task_id = task_id_by_candidate_revision_id.get(candidate_revision_id)
        if task_id is None:
            raise ValueError("candidate style evidence has no frozen revision")
        memory_record_id = int(evidence["memory_record_id"])
        item = grouped.setdefault(
            memory_record_id,
            {
                "memory_record_id": memory_record_id,
                "memory_text": str(evidence.get("memory_text") or "").strip(),
                "memory_text_hash": str(evidence.get("memory_text_hash") or ""),
                "supporting_task_ids": set(),
                "memory_evidence_ids": [],
            },
        )
        if not item["memory_text"]:
            raise ValueError("candidate style rule is empty")
        item["supporting_task_ids"].add(task_id)
        item["memory_evidence_ids"].append(int(evidence["memory_evidence_id"]))
    rules = []
    for item in grouped.values():
        supporting_task_ids = sorted(item.pop("supporting_task_ids"))
        item["supporting_task_ids"] = supporting_task_ids
        item["supporting_task_count"] = len(supporting_task_ids)
        item["memory_evidence_ids"] = sorted(set(item["memory_evidence_ids"]))
        rules.append(item)
    return sorted(rules, key=lambda item: item["memory_record_id"])


def _candidate_generation_input(
    frozen: Mapping[str, object],
    style_rules: list[dict],
) -> dict:
    build = frozen["build"]
    base_version = frozen.get("base_version")
    samples = frozen.get("revision_samples")
    if not isinstance(base_version, Mapping) or not isinstance(samples, list):
        raise ValueError("candidate base version or samples are missing")
    revision_edits = []
    for sample in samples:
        revision_edits.append(
            {
                "task_id": int(sample["task_id"]),
                "revision_id": int(sample["revision_id"]),
                "ai_original": str(sample.get("generated_feedback_text") or ""),
                "teacher_final": str(sample.get("final_feedback_text") or ""),
                "generation_diff": sample.get("generation_diff") or {},
                "previous_revision_diff": sample.get("previous_revision_diff"),
            }
        )
    return {
        "skill": frozen.get("skill") if isinstance(frozen.get("skill"), Mapping) else {},
        "base_skill": {
            "version_id": int(base_version["id"]),
            "content": str(base_version.get("content") or ""),
            "content_hash": str(base_version.get("content_hash") or ""),
        },
        "source_snapshot_hash": str(build["source_snapshot_hash"]),
        "style_rules": style_rules,
        "revision_edits": revision_edits,
        "rules": [
            "Use all frozen revision_edits as the primary evidence.",
            "Treat style_rules as optional extracted hints, not as an eligibility gate.",
            "Do not put any student or lesson fact into the skill.",
            "Return the complete skill with the smallest supported edit.",
            "Preserve the colleague identity and all unrelated persona, work, and assessment instructions.",
        ],
    }


def _default_candidate_generator(
    candidate_input: dict,
    config: Mapping[str, object],
):
    return ai_processor.generate_class_commentary_skill_candidate(
        candidate_input=candidate_input,
        **_class_commentary_ai_kwargs(config),
    )


def _replace_active_skill_content(
    prompt_payload: Mapping[str, object],
    candidate_content: str,
) -> dict:
    request_payload = deepcopy(dict(prompt_payload))
    messages = request_payload.get("messages")
    if not isinstance(messages, list):
        raise ValueError("frozen replay prompt has no messages")
    marker = re.compile(
        r"(\[ACTIVE_SKILL\]\n)(.*?)(\n\n\[TEACHER_STYLE_MEMORIES\])",
        re.DOTALL,
    )
    replacements = 0
    for message in messages:
        if not isinstance(message, dict) or str(message.get("role") or "") != "user":
            continue
        content = str(message.get("content") or "")
        match = marker.search(content)
        if not match:
            continue
        try:
            skill_payload = json.loads(match.group(2))
        except json.JSONDecodeError as exc:
            raise ValueError("frozen active skill payload is invalid") from exc
        if not isinstance(skill_payload, dict):
            raise ValueError("frozen active skill payload is invalid")
        skill_payload["content"] = candidate_content
        serialized_skill = json.dumps(
            skill_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        message["content"] = (
            content[: match.start(2)] + serialized_skill + content[match.end(2) :]
        )
        replacements += 1
    if replacements != 1:
        raise ValueError("frozen replay prompt must contain one active skill block")
    return request_payload


def _default_replay_generator(
    sample: Mapping[str, object],
    candidate_content: str,
    config: Mapping[str, object],
):
    prompt_payload = sample.get("prompt_payload")
    if not isinstance(prompt_payload, Mapping):
        raise ValueError("frozen replay prompt is missing")
    chat_request = _replace_active_skill_content(prompt_payload, candidate_content)
    return ai_processor.generate_class_commentary_feedback(
        class_record={"id": 1},
        students=[],
        transcript_text="",
        skill={},
        chat_request=chat_request,
        **_class_commentary_ai_kwargs(config),
    )


def _default_replay_evaluator(
    evaluation_input: dict,
    config: Mapping[str, object],
):
    return ai_processor.evaluate_class_commentary_skill_candidate_replays(
        evaluation_input=evaluation_input,
        **_class_commentary_ai_kwargs(config),
    )


def _split_ai_result(result: object) -> tuple[object, dict]:
    if isinstance(result, tuple) and len(result) == 2:
        payload, usage = result
        return payload, dict(usage) if isinstance(usage, Mapping) else {}
    return result, {}


def _normalized_edit_distance(left: object, right: object) -> float:
    left_text = " ".join(str(left or "").split())
    right_text = " ".join(str(right or "").split())
    if not left_text and not right_text:
        return 0.0
    return round(1.0 - SequenceMatcher(None, left_text, right_text).ratio(), 6)


def _normalize_candidate_payload(
    payload: object,
    *,
    allowed_style_record_ids: set[int],
) -> dict:
    if not isinstance(payload, Mapping):
        raise ValueError("candidate generator returned an invalid payload")
    content = str(payload.get("candidate_content") or "").strip()
    if not content or len(content) > 200000:
        raise ValueError("candidate skill content is invalid")
    change_summary = payload.get("change_summary")
    known_risks = payload.get("known_risks")
    incorporated = payload.get("incorporated_memory_record_ids")
    if not isinstance(change_summary, list) or not isinstance(known_risks, list):
        raise ValueError("candidate summary or risks are invalid")
    if not isinstance(incorporated, list):
        raise ValueError("candidate style rule IDs are invalid")
    normalized_summary = [str(value or "").strip() for value in change_summary]
    normalized_risks = [str(value or "").strip() for value in known_risks]
    if not normalized_summary or any(
        not value for value in normalized_summary + normalized_risks
    ):
        raise ValueError("candidate summary and risks must not contain empty values")
    if any(isinstance(value, bool) for value in incorporated):
        raise ValueError("candidate style rule IDs are invalid")
    try:
        normalized_ids = sorted({int(value) for value in incorporated})
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate style rule IDs are invalid") from exc
    if not set(normalized_ids).issubset(allowed_style_record_ids):
        raise ValueError("candidate used an unfrozen style rule")
    return {
        "candidate_content": content,
        "change_summary": normalized_summary[:20],
        "known_risks": normalized_risks[:20],
        "incorporated_memory_record_ids": normalized_ids,
    }


def _normalize_replay_judgments(
    payload: object,
    *,
    samples: list[dict],
    allowed_style_record_ids: set[int],
) -> dict[tuple[int, int], dict]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("samples"), list):
        raise ValueError("candidate replay evaluator returned an invalid payload")
    expected = {
        (int(sample["task_id"]), int(sample["revision_id"])) for sample in samples
    }
    normalized = {}
    boolean_fields = (
        "base_roster_consistent",
        "candidate_roster_consistent",
        "base_plain_text_valid",
        "candidate_plain_text_valid",
        "base_structure_valid",
        "candidate_structure_valid",
    )
    for item in payload["samples"]:
        if not isinstance(item, Mapping):
            raise ValueError("candidate replay judgment is invalid")
        key = (int(item.get("task_id") or 0), int(item.get("revision_id") or 0))
        if key not in expected or key in normalized:
            raise ValueError("candidate replay judgment scope is invalid")
        for field in boolean_fields:
            if not isinstance(item.get(field), bool):
                raise ValueError("candidate replay judgment boolean is invalid")
        counts = {}
        for field in ("base_unsupported_fact_count", "candidate_unsupported_fact_count"):
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("candidate replay unsupported fact count is invalid")
            counts[field] = value
        raw_style_ids = item.get("candidate_style_memory_record_ids")
        if not isinstance(raw_style_ids, list):
            raise ValueError("candidate replay style IDs are invalid")
        try:
            style_ids = sorted({int(value) for value in raw_style_ids})
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate replay style IDs are invalid") from exc
        if not set(style_ids).issubset(allowed_style_record_ids):
            raise ValueError("candidate replay used an unfrozen style rule")
        normalized[key] = {
            **{field: bool(item[field]) for field in boolean_fields},
            **counts,
            "candidate_style_memory_record_ids": style_ids,
        }
    if set(normalized) != expected:
        raise ValueError("candidate replay evaluator omitted frozen samples")
    return normalized


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _rate(values: list[bool]) -> float:
    return round(sum(1 for value in values if value) / len(values), 6) if values else 0.0


def process_class_commentary_skill_candidate_build(
    build_id: int,
    *,
    store=None,
    candidate_generator=None,
    replay_generator=None,
    replay_evaluator=None,
    runtime_config: Optional[Mapping[str, object]] = None,
    claim_owner: Optional[str] = None,
) -> dict:
    config = _runtime_config(runtime_config)
    if not _enabled(config):
        return {"enabled": False, "status": "disabled", "build_id": int(build_id)}
    target_store = _store(store)
    default_owner, _ = _rq_context()
    claimed = target_store.claim_class_commentary_skill_candidate_build(
        int(build_id),
        claim_owner=claim_owner or default_owner,
    )
    if not claimed:
        return {"enabled": True, "status": "not_claimed", "build_id": int(build_id)}
    claim_token = str(claimed["claim_token"])
    try:
        frozen = target_store.get_class_commentary_skill_candidate_build_input(
            int(build_id)
        )
        if not isinstance(frozen, Mapping):
            raise ValueError("candidate frozen input is missing")
        if frozen.get("source_valid") is not True:
            failed = target_store.fail_class_commentary_skill_candidate_build(
                int(build_id),
                claim_token=claim_token,
                error=str(frozen.get("stale_reason") or "candidate_stale"),
            )
            return {
                "enabled": True,
                "status": str((failed or {}).get("status") or "obsolete"),
                "build_id": int(build_id),
            }
        style_rules = _candidate_style_rules(frozen)
        allowed_style_record_ids = {
            int(rule["memory_record_id"]) for rule in style_rules
        }
        generate = candidate_generator or _default_candidate_generator
        candidate_result, candidate_usage = _split_ai_result(
            generate(_candidate_generation_input(frozen, style_rules), config)
        )
        candidate = _normalize_candidate_payload(
            candidate_result,
            allowed_style_record_ids=allowed_style_record_ids,
        )
        base_version = frozen.get("base_version")
        base_content = str(
            base_version.get("content") if isinstance(base_version, Mapping) else ""
        ).strip()
        candidate_content = candidate["candidate_content"]
        if candidate_content == base_content:
            raise ValueError("candidate skill did not change")
        roster_names = [
            str(item.get("student_name") or item.get("name") or "").strip()
            for sample in frozen.get("revision_samples", [])
            for item in sample.get("attending_roster", [])
            if isinstance(item, Mapping)
        ]
        if contains_class_commentary_private_information(candidate_content):
            raise ValueError("candidate skill contains private information")
        if contains_class_commentary_roster_name([candidate_content], roster_names):
            raise ValueError("candidate skill contains a roster name")

        replay = replay_generator or _default_replay_generator
        replay_samples = []
        replay_usage = []
        for sample in frozen.get("revision_samples", []):
            candidate_output, usage = _split_ai_result(
                replay(sample, candidate_content, config)
            )
            candidate_output = str(candidate_output or "").strip()
            if not candidate_output:
                raise ValueError("candidate replay returned empty feedback")
            replay_usage.append(usage)
            replay_samples.append(
                {
                    "task_id": int(sample["task_id"]),
                    "revision_id": int(sample["revision_id"]),
                    "transcript": str(sample.get("confirmed_transcript_snapshot") or ""),
                    "roster": sample.get("attending_roster") or [],
                    "teacher_final": str(sample.get("final_feedback_text") or ""),
                    "base_output": str(sample.get("generated_feedback_text") or ""),
                    "candidate_output": candidate_output,
                    "accepted_without_edit": bool(sample.get("accepted_without_edit")),
                }
            )
        evaluate = replay_evaluator or _default_replay_evaluator
        evaluator_result, evaluator_usage = _split_ai_result(
            evaluate(
                {
                    "candidate_skill_content": candidate_content,
                    "style_rules": style_rules,
                    "samples": replay_samples,
                },
                config,
            )
        )
        if not isinstance(evaluator_result, Mapping):
            raise ValueError("candidate replay evaluator returned an invalid payload")
        candidate_skill_student_fact_count = evaluator_result.get(
            "candidate_skill_student_fact_count"
        )
        if (
            isinstance(candidate_skill_student_fact_count, bool)
            or not isinstance(candidate_skill_student_fact_count, int)
            or candidate_skill_student_fact_count < 0
        ):
            raise ValueError("candidate skill contamination count is invalid")
        if candidate_skill_student_fact_count:
            raise ValueError("candidate skill contains a student fact")
        judgments = _normalize_replay_judgments(
            evaluator_result,
            samples=replay_samples,
            allowed_style_record_ids=allowed_style_record_ids,
        )
        evaluated_samples = []
        covered_style_ids = set()
        for sample in replay_samples:
            key = (sample["task_id"], sample["revision_id"])
            judgment = judgments[key]
            covered_style_ids.update(judgment["candidate_style_memory_record_ids"])
            evaluated_samples.append(
                {
                    "task_id": sample["task_id"],
                    "revision_id": sample["revision_id"],
                    "accepted_without_edit": sample["accepted_without_edit"],
                    "base_normalized_edit_distance": _normalized_edit_distance(
                        sample["base_output"], sample["teacher_final"]
                    ),
                    "candidate_normalized_edit_distance": _normalized_edit_distance(
                        sample["candidate_output"], sample["teacher_final"]
                    ),
                    "base_exact_acceptance": " ".join(sample["base_output"].split())
                    == " ".join(sample["teacher_final"].split()),
                    "candidate_exact_acceptance": " ".join(
                        sample["candidate_output"].split()
                    )
                    == " ".join(sample["teacher_final"].split()),
                    **judgment,
                }
            )
        base_distances = [
            item["base_normalized_edit_distance"] for item in evaluated_samples
        ]
        candidate_distances = [
            item["candidate_normalized_edit_distance"] for item in evaluated_samples
        ]
        no_edit_samples = [
            item for item in evaluated_samples if item["accepted_without_edit"]
        ]
        build = frozen["build"]
        evaluation_snapshot = {
            "schema_version": "class_commentary_skill_evaluation.v1",
            "source_snapshot_hash": str(build["source_snapshot_hash"]),
            "effective_task_count": int(build["effective_task_count"]),
            "supporting_task_count": int(build["supporting_task_count"]),
            "incorporated_memory_record_ids": candidate[
                "incorporated_memory_record_ids"
            ],
            "change_summary": candidate["change_summary"],
            "known_risks": candidate["known_risks"],
            "metrics": {
                "base": {
                    "normalized_edit_distance": _average(base_distances),
                    "exact_acceptance_rate": _rate(
                        [item["base_exact_acceptance"] for item in evaluated_samples]
                    ),
                    "no_edit_acceptance_rate": _rate(
                        [item["base_exact_acceptance"] for item in no_edit_samples]
                    ),
                    "roster_consistency_rate": _rate(
                        [item["base_roster_consistent"] for item in evaluated_samples]
                    ),
                    "unsupported_fact_count": sum(
                        item["base_unsupported_fact_count"]
                        for item in evaluated_samples
                    ),
                    "output_constraint_pass_rate": _rate(
                        [
                            item["base_plain_text_valid"]
                            and item["base_structure_valid"]
                            for item in evaluated_samples
                        ]
                    ),
                },
                "candidate": {
                    "normalized_edit_distance": _average(candidate_distances),
                    "exact_acceptance_rate": _rate(
                        [item["candidate_exact_acceptance"] for item in evaluated_samples]
                    ),
                    "no_edit_acceptance_rate": _rate(
                        [item["candidate_exact_acceptance"] for item in no_edit_samples]
                    ),
                    "confirmed_style_rule_coverage_rate": (
                        round(len(covered_style_ids) / len(allowed_style_record_ids), 6)
                        if allowed_style_record_ids
                        else 0.0
                    ),
                    "roster_consistency_rate": _rate(
                        [
                            item["candidate_roster_consistent"]
                            for item in evaluated_samples
                        ]
                    ),
                    "unsupported_fact_count": sum(
                        item["candidate_unsupported_fact_count"]
                        for item in evaluated_samples
                    ),
                    "student_fact_contamination_count": candidate_skill_student_fact_count,
                    "output_constraint_pass_rate": _rate(
                        [
                            item["candidate_plain_text_valid"]
                            and item["candidate_structure_valid"]
                            for item in evaluated_samples
                        ]
                    ),
                },
                "delta": {
                    "normalized_edit_distance_improvement": round(
                        _average(base_distances) - _average(candidate_distances), 6
                    )
                },
            },
            "samples": evaluated_samples,
            "usage": {
                "candidate_generation": candidate_usage,
                "candidate_replays": replay_usage,
                "replay_evaluation": evaluator_usage,
            },
        }
        completed = target_store.complete_class_commentary_skill_candidate_build(
            int(build_id),
            claim_token=claim_token,
            candidate_content=candidate_content,
            evaluation_snapshot=evaluation_snapshot,
        )
    except Exception as exc:
        try:
            target_store.fail_class_commentary_skill_candidate_build(
                int(build_id),
                claim_token=claim_token,
                error=str(exc),
            )
        except Exception:
            pass
        raise
    logger.info(
        "class commentary skill candidate build %s finished: status=%s",
        build_id,
        str((completed or {}).get("status") or "succeeded"),
    )
    return {
        "enabled": True,
        "status": str((completed or {}).get("status") or "succeeded"),
        "build_id": int(build_id),
        "candidate_version_id": (completed or {}).get("candidate_version_id"),
    }


def _projection_scope(target: Mapping[str, object]) -> dict:
    scope = {
        "organization_id": target.get("organization_id"),
        "memory_type": target.get("memory_type"),
    }
    if target.get("memory_type") == "teacher_style":
        scope["scope_skill_registry_id"] = target.get("scope_skill_registry_id")
    else:
        scope["student_id"] = target.get("student_id")
        scope["subject_key"] = target.get("subject_key")
    return scope


def _apply_operation(memory_service, operation: Mapping[str, object]) -> tuple[Optional[str], str]:
    target = operation.get("target_state")
    if not isinstance(target, Mapping):
        raise ValueError("memory operation target_state is missing")
    metadata = operation.get("projection_metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("memory operation projection_metadata is missing")
    metadata = dict(metadata)
    metadata.setdefault(
        "status",
        str(metadata.get("desired_status") or target.get("desired_status") or "unknown"),
    )
    operation_key = str(operation.get("operation_key") or "")
    existing = memory_service.find_by_operation_key(operation_key, **_projection_scope(target))
    if existing is not None:
        return str(existing.get("id") or "") or None, str(target.get("desired_status") or "active")

    operation_type = str(operation.get("operation_type") or "")
    desired_status = str(target.get("desired_status") or "")
    mem0_memory_id = str(operation.get("mem0_memory_id") or "").strip() or None
    if operation_type == "delete" or desired_status == "deleted":
        if mem0_memory_id and memory_service.get(mem0_memory_id) is not None:
            memory_service.delete(mem0_memory_id)
        return mem0_memory_id, "deleted"
    if desired_status in {"superseded", "revoked"} and not mem0_memory_id:
        return None, desired_status
    if not mem0_memory_id:
        projection = memory_service.add_projection(
            memory_text=str(target.get("memory_text") or ""),
            metadata=metadata,
        )
        return str(projection["id"]), desired_status or "active"
    memory_service.update(
        mem0_memory_id,
        memory_text=str(target.get("memory_text") or ""),
        metadata=metadata,
    )
    return mem0_memory_id, desired_status or "active"


def process_class_commentary_memory_operation(
    operation_id: int,
    *,
    store=None,
    memory_service=None,
    runtime_config: Optional[Mapping[str, object]] = None,
    lease_owner: Optional[str] = None,
    rq_job_id: Optional[str] = None,
) -> dict:
    config = _runtime_config(runtime_config)
    if not _enabled(config):
        return {"enabled": False, "status": "disabled", "operation_id": int(operation_id)}

    target_store = _store(store)
    default_owner, current_rq_job_id = _rq_context()
    timeout = int(config.get("class_commentary_memory_operation_timeout") or 120)
    claimed = target_store.claim_class_commentary_memory_operation(
        int(operation_id),
        lease_owner=lease_owner or default_owner,
        rq_job_id=rq_job_id or current_rq_job_id,
        lease_seconds=2 * timeout,
    )
    if not claimed:
        return {"enabled": True, "status": "not_claimed", "operation_id": int(operation_id)}

    lease_token = str(claimed["lease_token"])
    try:
        service = memory_service or ClassCommentaryMemoryService(runtime_config=config)
        mem0_memory_id, applied_status = _apply_operation(service, claimed)
    except Exception as exc:
        try:
            target_store.fail_class_commentary_memory_operation(
                int(operation_id), lease_token=lease_token, error=str(exc)
            )
        except Exception:
            logger.exception(
                "memory operation %s failed and could not be marked failed",
                operation_id,
            )
        raise

    try:
        completed = target_store.complete_class_commentary_memory_operation(
            int(operation_id),
            lease_token=lease_token,
            mem0_memory_id=mem0_memory_id,
            applied_status=applied_status,
            projection_metadata=claimed.get("projection_metadata"),
        )
    except Exception as exc:
        try:
            target_store.fail_class_commentary_memory_operation(
                int(operation_id),
                lease_token=lease_token,
                error=str(exc),
                mem0_succeeded=True,
                mem0_memory_id=mem0_memory_id,
            )
        except Exception:
            pass
        raise
    logger.info(
        "class commentary memory operation %s applied: status=%s mem0_memory_id=%s",
        operation_id,
        str((completed or {}).get("status") or "applied"),
        mem0_memory_id or "-",
    )
    return {
        "enabled": True,
        "status": str((completed or {}).get("status") or "applied"),
        "operation_id": int(operation_id),
        "mem0_memory_id": mem0_memory_id,
    }


def _active_rq_job_ids(queue) -> list[str]:
    registry = getattr(queue, "started_job_registry", None)
    if registry is None:
        return []
    get_job_ids = getattr(registry, "get_job_ids", None)
    if not callable(get_job_ids):
        return []
    return [str(job_id) for job_id in get_job_ids()]


def _active_candidate_build_ids(rq_job_ids: list[str]) -> set[int]:
    active_ids = set()
    for job_id in rq_job_ids:
        match = re.fullmatch(r"cc-skill-candidate-(\d+)-a\d+", str(job_id))
        if match:
            active_ids.add(int(match.group(1)))
    return active_ids


def run_class_commentary_memory_reconciliation(
    *,
    store=None,
    queue=None,
    runtime_config: Optional[Mapping[str, object]] = None,
    now: Optional[datetime] = None,
) -> dict:
    config = _runtime_config(runtime_config)
    if not _enabled(config):
        return {"enabled": False, "status": "disabled"}

    from class_commentary_memory_queue import (
        dispatch_class_commentary_memory_work,
        ensure_class_commentary_memory_reconciliation_scheduled,
        get_class_commentary_memory_queue,
    )

    target_store = _store(store)
    target_queue = queue or get_class_commentary_memory_queue(runtime_config=config)
    try:
        scheduled = ensure_class_commentary_memory_reconciliation_scheduled(
            queue=target_queue,
            runtime_config=config,
            now=now or datetime.now(timezone.utc),
        )
    except Exception as exc:
        logger.warning(
            "class commentary memory reconciliation could not schedule the next bucket: %s",
            type(exc).__name__,
        )
        scheduled = {"scheduled": False, "error_type": exc.__class__.__name__}
    active_rq_job_ids = _active_rq_job_ids(target_queue)
    reconciled = target_store.reconcile_class_commentary_memory_store(
        active_rq_job_ids=active_rq_job_ids,
        now=now,
        limit=100,
    )
    candidate_recoverer = getattr(
        target_store,
        "recover_stale_class_commentary_skill_candidate_builds",
        None,
    )
    recovered_candidates = (
        candidate_recoverer(
            timeout_seconds=int(config.get("skill_evolution_build_timeout") or 300),
            active_build_ids=_active_candidate_build_ids(active_rq_job_ids),
            now=now,
        )
        if callable(candidate_recoverer)
        else []
    )
    student_run_recoverer = getattr(
        target_store,
        "recover_stale_class_commentary_student_generation_runs",
        None,
    )
    recovered_student_runs = (
        student_run_recoverer(
            now=now,
            max_attempts=int(
                config.get("class_commentary_student_generation_max_attempts") or 3
            ),
        )
        if callable(student_run_recoverer)
        else []
    )
    batch_lister = getattr(
        target_store,
        "list_resumable_class_commentary_batch_generations",
        None,
    )
    resumable_batches = batch_lister(limit=100, now=now) if callable(batch_lister) else []
    recovered_batch_generations = []
    for generation in resumable_batches:
        try:
            from class_commentary_batch_generation_jobs import (
                process_class_commentary_batch_generation,
            )

            resumed = process_class_commentary_batch_generation(
                int(generation["id"]),
                store=target_store,
                runtime_config=config,
            )
            recovered_batch_generations.append(
                {
                    "generation_id": int(generation["id"]),
                    "status": str(resumed.get("status") or ""),
                }
            )
        except Exception as exc:
            logger.warning(
                "class commentary batch generation %s resume failed: %s",
                generation["id"],
                type(exc).__name__,
            )
            recovered_batch_generations.append(
                {
                    "generation_id": int(generation["id"]),
                    "status": "retry_pending",
                    "error_type": exc.__class__.__name__,
                }
            )
    try:
        dispatched = dispatch_class_commentary_memory_work(
            store=target_store,
            queue=target_queue,
            runtime_config=config,
        )
    except Exception as exc:
        logger.warning(
            "class commentary memory dispatch failed during reconciliation: %s",
            type(exc).__name__,
        )
        dispatched = {"queued": False, "error_type": exc.__class__.__name__}
    logger.info(
        "class commentary memory reconciliation completed: recovered_candidates=%d recovered_student_runs=%d recovered_batch_generations=%d dispatch_errors=%d",
        len(recovered_candidates),
        len(recovered_student_runs),
        len(recovered_batch_generations),
        len(dispatched.get("errors") or []),
    )
    return {
        "enabled": True,
        "status": "completed",
        "scheduled": scheduled,
        "reconciled": reconciled,
        "recovered_candidates": recovered_candidates,
        "recovered_student_runs": recovered_student_runs,
        "recovered_batch_generations": recovered_batch_generations,
        "dispatched": dispatched,
    }
