from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Optional

from rq import get_current_job

import config_runtime
from ai_processor import generate_class_commentary_feedback
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
    ClassCommentaryStructuredFeedbackValidationError,
)
from class_commentary_memory import ClassCommentaryMemoryService
from class_commentary_memory_retrieval import (
    ClassCommentaryStudentMemoryRetrievalError,
    retrieve_isolated_student_memory_context,
    validate_isolated_student_memory_context_snapshot,
)
from class_commentary_student_memory_v2 import (
    CLASS_COMMENTARY_STUDENT_RUN_SCHEMA_V1,
    build_isolated_student_chat_request,
    canonical_hash,
    canonical_json,
    content_hash,
    validate_isolated_prompt_privacy,
    validate_single_student_response,
)
from credit_manager import CreditBalanceError, finalize_ai_charge


def _runtime_config(runtime_config: Optional[Mapping[str, object]] = None) -> dict:
    return dict(
        runtime_config
        if runtime_config is not None
        else config_runtime.get_runtime_config()
    )


def _store(store=None):
    if store is not None:
        return store
    import lesson_manager

    return lesson_manager


def _rq_context() -> tuple[str, str]:
    job = get_current_job()
    if job is None:
        return "class-commentary-student-generation", ""
    return f"rq:{job.id}", str(job.id)


def _json_object(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        parsed = {}
    if not isinstance(parsed, dict):
        raise ValueError("student generation snapshot is invalid")
    return parsed


def _json_list(value: object) -> list:
    if isinstance(value, list):
        return list(value)
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, json.JSONDecodeError):
        parsed = []
    if not isinstance(parsed, list):
        raise ValueError("student generation list snapshot is invalid")
    return parsed


def _validate_run_contract(run: Mapping[str, object], generation: Mapping[str, object]) -> None:
    expected_eligible_ids = _json_list(generation.get("eligible_student_ids_json"))
    saved_eligible_ids = _json_list(run.get("eligible_student_ids_json"))
    checks = (
        str(run.get("student_run_schema_version") or "")
        == CLASS_COMMENTARY_STUDENT_RUN_SCHEMA_V1,
        str(run.get("memory_mode") or "")
        == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
        str(generation.get("student_history_memory_mode") or "")
        == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
        str(run.get("prompt_version") or "")
        == str(generation.get("prompt_version") or ""),
        str(run.get("provider") or "")
        == str(generation.get("model_provider") or ""),
        str(run.get("model") or "") == str(generation.get("model_name") or ""),
        str(run.get("model_parameters_json") or "")
        == str(generation.get("model_parameters_json") or ""),
        saved_eligible_ids == expected_eligible_ids,
        int(run.get("student_id") or 0) in expected_eligible_ids,
        str(run.get("eligible_student_scope_hash") or "")
        == str(generation.get("eligible_student_scope_hash") or ""),
        str(run.get("student_mention_matcher_version") or "")
        == str(generation.get("student_mention_matcher_version") or ""),
    )
    if not all(checks):
        raise ValueError("student generation frozen contract mismatch")


def _validate_evidence_snapshot(
    *,
    run: Mapping[str, object],
    generation: Mapping[str, object],
    evidence_snapshot: Mapping[str, object],
) -> None:
    if canonical_hash(evidence_snapshot) != str(run.get("current_evidence_hash") or ""):
        raise ValueError("student evidence snapshot hash mismatch")
    transcript = str(generation.get("confirmed_transcript_snapshot") or "")
    transcript_hash = str(generation.get("confirmed_transcript_hash") or "")
    if (
        content_hash(transcript) != transcript_hash
        or str(evidence_snapshot.get("transcript_hash") or "") != transcript_hash
        or str(evidence_snapshot.get("matcher_version") or "")
        != str(run.get("student_mention_matcher_version") or "")
    ):
        raise ValueError("student evidence transcript contract mismatch")
    fragments = evidence_snapshot.get("fragments")
    if not isinstance(fragments, list):
        raise ValueError("student evidence fragments are invalid")
    for fragment in fragments:
        if not isinstance(fragment, Mapping):
            raise ValueError("student evidence fragment is invalid")
        start = int(fragment.get("start") or 0)
        end = int(fragment.get("end") or 0)
        text = str(fragment.get("text") or "")
        if (
            start < 0
            or end <= start
            or transcript[start:end] != text
            or content_hash(text) != str(fragment.get("text_hash") or "")
        ):
            raise ValueError("student evidence fragment provenance mismatch")


def _usage_payload(value: object, *, provider: str, model: str) -> dict:
    payload = value if isinstance(value, dict) else {}
    return {
        "provider": str(payload.get("provider") or provider),
        "model": str(payload.get("model") or model),
        "input_tokens": max(0, int(payload.get("input_tokens") or 0)),
        "output_tokens": max(0, int(payload.get("output_tokens") or 0)),
    }


def _split_result(result: object, *, provider: str, model: str) -> tuple[str, dict]:
    if isinstance(result, tuple) and len(result) == 2:
        return str(result[0] or ""), _usage_payload(
            result[1], provider=provider, model=model
        )
    return str(result or ""), _usage_payload({}, provider=provider, model=model)


def _retry_after_seconds(exc: Exception, default: int = 30) -> int:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or getattr(exc, "headers", None)
    value = None
    if isinstance(headers, Mapping):
        value = headers.get("retry-after") or headers.get("Retry-After")
    try:
        parsed = int(float(str(value))) if value is not None else int(default)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(1, min(parsed, 600))


def _provider_error(exc: Exception) -> tuple[str, bool, int]:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    response = getattr(exc, "response", None)
    raw_status = getattr(exc, "status_code", None) or getattr(
        response, "status_code", None
    )
    try:
        status_code = int(raw_status) if raw_status is not None else 0
    except (TypeError, ValueError):
        status_code = 0
    if "ratelimit" in name or "rate limit" in message or "429" in message:
        return "provider_rate_limited", True, _retry_after_seconds(exc, 60)
    if "timeout" in name or "timed out" in message or "timeout" in message:
        return "provider_timeout", True, _retry_after_seconds(exc, 30)
    if "connection" in name or "connection" in message or "temporar" in message:
        return "provider_unavailable", True, _retry_after_seconds(exc, 30)
    if 400 <= status_code < 500 and status_code not in {408, 409, 425, 429}:
        return "provider_request_rejected", False, 0
    return "provider_request_failed", True, _retry_after_seconds(exc, 30)


def _openai_api_key(config: Mapping[str, object]) -> str:
    return str(
        config.get("class_commentary_openai_api_key")
        or config.get("openai_api_key")
        or ""
    ).strip()


def _record_loader(store, generation: Mapping[str, object]):
    return lambda record_ids: store.get_class_commentary_memory_records_by_ids(
        record_ids,
        organization_id=int(generation["organization_id"]),
    )


def _reconciliation_marker(store):
    return lambda organization_id, record_ids, reason: (
        store.mark_class_commentary_memory_records_reconcile_needed(
            record_ids,
            reason,
            organization_id=organization_id,
        )
    )


def _defer_or_fail_charge(
    *,
    store,
    run: Mapping[str, object],
    claim_token: str,
    exc: Exception,
) -> dict:
    if exc.__class__.__name__ == "AiUsageRequestConflict":
        failed = store.fail_class_commentary_student_generation_charge(
            int(run["id"]),
            claim_token=claim_token,
            error_code="charge_request_conflict",
        )
        store.finalize_class_commentary_student_generation_parent(
            int(run["generation_id"])
        )
        return failed
    error_code = (
        "charge_pending_insufficient_credits"
        if isinstance(exc, CreditBalanceError)
        else "charge_pending_retry"
    )
    return store.defer_class_commentary_student_generation_charge(
        int(run["id"]),
        claim_token=claim_token,
        error_code=error_code,
        retry_after_seconds=300,
    )


def _schedule_retry_best_effort(
    run: Mapping[str, object],
    *,
    config: Mapping[str, object],
    delay_seconds: int,
) -> None:
    if get_current_job() is None:
        return
    try:
        from class_commentary_memory_queue import (
            enqueue_class_commentary_student_generation_run,
            get_class_commentary_memory_queue,
        )

        queue = get_class_commentary_memory_queue(runtime_config=config)
        enqueue_class_commentary_student_generation_run(
            run,
            queue=queue,
            runtime_config=config,
            delay_seconds=max(1, int(delay_seconds)),
        )
    except Exception:
        pass


def process_class_commentary_student_generation_run(
    run_id: int,
    *,
    store=None,
    runtime_config: Optional[Mapping[str, object]] = None,
    memory_service=None,
    generator=None,
    charge_finalizer=None,
    claim_owner: Optional[str] = None,
) -> dict:
    config = _runtime_config(runtime_config)
    target_store = _store(store)
    default_owner, rq_job_id = _rq_context()
    timeout = int(config.get("class_commentary_student_generation_timeout") or 300)
    claimed = target_store.claim_class_commentary_student_generation_run(
        int(run_id),
        claim_owner=claim_owner or default_owner,
        lease_seconds=2 * timeout,
    )
    if not claimed:
        return {"status": "not_claimed", "run_id": int(run_id)}
    claim_token = str(claimed["claim_token"])
    generation = target_store.get_class_commentary_generation(
        int(claimed["generation_id"])
    )
    if not generation:
        failed = target_store.fail_class_commentary_student_generation_run(
            int(run_id),
            claim_token=claim_token,
            error_code="generation_unavailable",
            retryable=False,
        )
        return {"status": failed["status"], "run_id": int(run_id)}
    provider_started = False
    try:
        access = target_store.validate_class_commentary_student_generation_access(
            int(run_id)
        )
        if not access.get("allowed"):
            failed = target_store.fail_class_commentary_student_generation_run(
                int(run_id),
                claim_token=claim_token,
                error_code=str(access.get("reason") or "student_access_revoked"),
                retryable=False,
            )
            target_store.finalize_class_commentary_student_generation_parent(
                int(generation["id"])
            )
            return {"status": failed["status"], "run_id": int(run_id)}

        _validate_run_contract(claimed, generation)
        roster = _json_list(generation.get("attending_roster_snapshot_json"))
        target_student_id = int(claimed["student_id"])
        target_student_name = str(claimed.get("student_name_snapshot") or "")
        other_students = [
            item
            for item in roster
            if isinstance(item, dict)
            and int(item.get("student_id") or 0) != target_student_id
        ]
        evidence_snapshot = _json_object(
            claimed.get("current_evidence_snapshot_json")
        )
        class_context = _json_object(claimed.get("class_context_snapshot_json"))
        if canonical_hash(class_context) != str(claimed.get("class_context_hash") or ""):
            raise ValueError("student class context hash mismatch")
        if set(class_context) != {"subject_key"}:
            raise ValueError("student class context contains unsafe fields")
        _validate_evidence_snapshot(
            run=claimed,
            generation=generation,
            evidence_snapshot=evidence_snapshot,
        )
        record_loader = _record_loader(target_store, generation)

        if str(claimed.get("status") or "") != "response_received":
            retrieval_status = str(claimed.get("memory_retrieval_status") or "pending")
            if retrieval_status == "pending":
                service = memory_service or ClassCommentaryMemoryService(
                    runtime_config=config
                )
                memory_context = retrieve_isolated_student_memory_context(
                    generation=generation,
                    student_id=target_student_id,
                    evidence_snapshot=evidence_snapshot,
                    class_context=class_context,
                    record_loader=record_loader,
                    memory_service=service,
                    reconciliation_marker=_reconciliation_marker(target_store),
                )
                chat_request = build_isolated_student_chat_request(
                    student_id=target_student_id,
                    student_name=target_student_name,
                    class_context=class_context,
                    evidence_snapshot=evidence_snapshot,
                    student_history_memories=memory_context.get(
                        "student_history_memories"
                    ),
                    teacher_style_memories=memory_context.get(
                        "teacher_style_memories"
                    ),
                    skill_content=str(generation.get("skill_content_snapshot") or ""),
                    model_parameters=_json_object(
                        claimed.get("model_parameters_json")
                    ),
                )
                validate_isolated_prompt_privacy(
                    chat_request=chat_request,
                    target_student_id=target_student_id,
                    target_student_name=target_student_name,
                    other_students=other_students,
                )
                claimed = target_store.finalize_class_commentary_student_generation_prompt(
                    int(run_id),
                    claim_token=claim_token,
                    memory_context=memory_context,
                    memory_retrieval_status=str(
                        memory_context.get("retrieval_status") or "empty"
                    ),
                    prompt_payload=chat_request,
                )
            else:
                memory_context = _json_object(
                    claimed.get("memory_context_snapshot_json")
                )
                chat_request = _json_object(
                    claimed.get("prompt_payload_snapshot_json")
                )
                if (
                    canonical_hash(memory_context)
                    != str(claimed.get("memory_context_hash") or "")
                    or canonical_hash(chat_request)
                    != str(claimed.get("prompt_payload_hash") or "")
                ):
                    raise ValueError("student prompt snapshot hash mismatch")
                validate_isolated_student_memory_context_snapshot(
                    generation=generation,
                    student_id=target_student_id,
                    memory_context=memory_context,
                    record_loader=record_loader,
                )
                validate_isolated_prompt_privacy(
                    chat_request=chat_request,
                    target_student_id=target_student_id,
                    target_student_name=target_student_name,
                    other_students=other_students,
                )

            evidence_text = "\n".join(
                str(fragment.get("text") or "")
                for fragment in evidence_snapshot.get("fragments", [])
                if isinstance(fragment, Mapping)
            )
            producer = generator or generate_class_commentary_feedback
            provider_started = True
            raw_result = producer(
                class_record=class_context,
                students=[
                    {"id": target_student_id, "name": target_student_name}
                ],
                transcript_text=evidence_text,
                skill={
                    "id": str(generation.get("skill_id") or ""),
                    "name": str(generation.get("skill_id") or ""),
                    "content": str(generation.get("skill_content_snapshot") or ""),
                },
                provider=str(claimed.get("provider") or ""),
                model=str(claimed.get("model") or ""),
                openai_api_key=_openai_api_key(config),
                openai_base_url=str(
                    config.get("class_commentary_openai_base_url")
                    or config.get("openai_base_url")
                    or ""
                ).strip(),
                openai_headers=str(
                    config.get("class_commentary_openai_headers") or ""
                ).strip(),
                chat_request=chat_request,
                request_id=str(claimed.get("request_id") or ""),
                include_usage=True,
            )
            response_text, usage = _split_result(
                raw_result,
                provider=str(claimed.get("provider") or ""),
                model=str(claimed.get("model") or ""),
            )
            validated = validate_single_student_response(
                response=response_text,
                target_student_id=target_student_id,
                target_student_name=target_student_name,
                other_students=other_students,
            )
            access_after = target_store.validate_class_commentary_student_generation_access(
                int(run_id)
            )
            if not access_after.get("allowed"):
                raise PermissionError(
                    str(access_after.get("reason") or "student_access_revoked")
                )
            claimed = target_store.persist_class_commentary_student_generation_response(
                int(run_id),
                claim_token=claim_token,
                response_snapshot={
                    "response_text": response_text,
                    "usage": usage,
                },
                structured_feedback_json=str(validated["structured_feedback_json"]),
                structured_feedback_hash=str(validated["structured_feedback_hash"]),
            )

        response_snapshot = _json_object(claimed.get("response_snapshot_json"))
        usage = _usage_payload(
            response_snapshot.get("usage"),
            provider=str(claimed.get("provider") or ""),
            model=str(claimed.get("model") or ""),
        )
        charge_payload_hash = canonical_hash(
            {
                "run_request_payload_hash": str(
                    claimed.get("request_payload_hash") or ""
                ),
                "response_hash": str(claimed.get("response_hash") or ""),
                "structured_feedback_hash": str(
                    claimed.get("structured_feedback_hash") or ""
                ),
                "usage": usage,
            }
        )
        charge = (charge_finalizer or finalize_ai_charge)(
            organization_id=int(claimed["organization_id"]),
            user_id=int(generation["teacher_user_id"]),
            feature_key="class_commentary_generate",
            usage=usage,
            source_record_type="class_commentary_student_generation_run",
            source_record_id=int(claimed["id"]),
            request_id=str(claimed["charge_request_key"]),
            request_payload_hash=charge_payload_hash,
        )
        completed = target_store.complete_class_commentary_student_generation_run(
            int(run_id),
            claim_token=claim_token,
            charge_usage_id=int(charge["id"]),
        )
        try:
            parent = target_store.finalize_class_commentary_student_generation_parent(
                int(generation["id"])
            )
        except Exception:
            parent = target_store.fail_class_commentary_generation(
                int(generation["id"]),
                "student_aggregate_invalid",
            )
        return {
            "status": completed["status"],
            "run_id": int(run_id),
            "generation_status": str(parent.get("status") or ""),
            "rq_job_id": rq_job_id,
        }
    except ClassCommentaryStudentMemoryRetrievalError as exc:
        error_code = str(exc) if str(exc).startswith("memory_") else "memory_retrieval_failed"
        retryable = error_code not in {"memory_snapshot_stale", "memory_snapshot_invalid"}
        retry_after = 30
    except ClassCommentaryStructuredFeedbackValidationError:
        error_code = "structured_feedback_invalid"
        retryable = False
        retry_after = 0
    except PermissionError as exc:
        reason = str(exc)
        error_code = reason if reason else "student_access_revoked"
        retryable = False
        retry_after = 0
    except Exception as exc:
        latest = target_store.get_class_commentary_student_generation_run(int(run_id))
        if latest and str(latest.get("status") or "") == "response_received":
            deferred = _defer_or_fail_charge(
                store=target_store,
                run=latest,
                claim_token=claim_token,
                exc=exc,
            )
            if str(deferred.get("status") or "") == "response_received":
                _schedule_retry_best_effort(
                    deferred,
                    config=config,
                    delay_seconds=300,
                )
            return {"status": deferred["status"], "run_id": int(run_id)}
        if provider_started:
            error_code, retryable, retry_after = _provider_error(exc)
        else:
            error_code = "student_run_contract_invalid"
            retryable = False
            retry_after = 0

    failed = target_store.fail_class_commentary_student_generation_run(
        int(run_id),
        claim_token=claim_token,
        error_code=error_code,
        retryable=retryable,
        max_attempts=int(
            config.get("class_commentary_student_generation_max_attempts") or 3
        ),
        retry_after_seconds=retry_after or 1,
    )
    if str(failed.get("status") or "") == "failed":
        target_store.finalize_class_commentary_student_generation_parent(
            int(generation["id"])
        )
    elif str(failed.get("status") or "") == "retry_wait":
        _schedule_retry_best_effort(
            failed,
            config=config,
            delay_seconds=retry_after or 1,
        )
    return {"status": failed["status"], "run_id": int(run_id)}
