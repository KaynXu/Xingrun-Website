from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
from collections.abc import Mapping
from typing import Optional

import ai_processor
import config_runtime
from class_commentary_feedback_schema import (
    ClassCommentaryStructuredFeedbackValidationError,
)
from class_commentary_batch_context import (
    build_batch_generation_execution_snapshot,
)
from class_commentary_memory import ClassCommentaryMemoryService
from class_commentary_provider_errors import (
    build_provider_dispatch_interruption_snapshot,
    build_provider_failure_snapshot,
)
from credit_manager import CreditBalanceError, finalize_ai_charge


logger = logging.getLogger(__name__)


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


def _claim_owner() -> str:
    return f"class-commentary-batch:{socket.gethostname()}:{os.getpid()}"


def _frozen_chat_request(generation: Mapping[str, object]) -> dict:
    raw_payload = str(generation.get("prompt_payload_snapshot_json") or "")
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("generation prompt snapshot is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("generation prompt snapshot is invalid")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != str(
        generation.get("prompt_payload_hash") or ""
    ):
        raise ValueError("generation prompt snapshot hash mismatch")
    return payload


def _usage_payload(value: object, *, provider: str, model: str) -> dict:
    usage = value if isinstance(value, dict) else {}
    return {
        "provider": str(usage.get("provider") or provider),
        "model": str(usage.get("model") or model),
        "input_tokens": max(0, int(usage.get("input_tokens") or 0)),
        "output_tokens": max(0, int(usage.get("output_tokens") or 0)),
    }


def _split_result(result: object, *, provider: str, model: str) -> tuple[str, dict]:
    if isinstance(result, tuple) and len(result) == 2:
        return str(result[0] or ""), _usage_payload(
            result[1], provider=provider, model=model
        )
    return str(result or ""), _usage_payload({}, provider=provider, model=model)


def _openai_api_key(config: Mapping[str, object]) -> str:
    return str(
        config.get("class_commentary_openai_api_key")
        or config.get("openai_api_key")
        or os.environ.get("OPENAI_API_KEY", "")
    ).strip()


def _default_generator(
    generation: Mapping[str, object],
    chat_request: dict,
    config: Mapping[str, object],
):
    return ai_processor.generate_class_commentary_feedback(
        class_record={},
        students=[],
        transcript_text="",
        skill={},
        provider=str(generation.get("model_provider") or ""),
        model=str(generation.get("model_name") or ""),
        openai_api_key=_openai_api_key(config),
        openai_base_url=str(
            config.get("class_commentary_openai_base_url")
            or config.get("openai_base_url")
            or ""
        ),
        openai_headers=str(config.get("class_commentary_openai_headers") or ""),
        chat_request=chat_request,
        request_id=f"class-commentary-generation-{int(generation['id'])}",
        request_timeout=float(
            config.get("class_commentary_batch_generation_timeout") or 300
        ),
        max_retries=0,
        include_usage=True,
    )


def _call_generator(generator, generation: Mapping[str, object], chat_request: dict, config: dict):
    if generator is None:
        return _default_generator(generation, chat_request, config)
    return generator(
        generation=generation,
        chat_request=chat_request,
        request_id=f"class-commentary-generation-{int(generation['id'])}",
        provider=str(generation.get("model_provider") or ""),
        model=str(generation.get("model_name") or ""),
        runtime_config=config,
    )


def _prepare_execution_snapshot(
    *,
    generation: Mapping[str, object],
    store,
    config: Mapping[str, object],
    memory_service=None,
    graph_adapter=None,
    graph_summary_loader=None,
) -> dict:
    organization_id = int(generation.get("organization_id") or 0)
    built = build_batch_generation_execution_snapshot(
        generation=generation,
        record_loader=lambda record_ids: store.get_class_commentary_memory_records_by_ids(
            record_ids,
            organization_id=organization_id,
        ),
        memory_service=(
            memory_service
            if memory_service is not None
            else ClassCommentaryMemoryService(runtime_config=dict(config))
        ),
        runtime_config=config,
        reconciliation_marker=(
            lambda marker_organization_id, record_ids, reason: (
                store.mark_class_commentary_memory_records_reconcile_needed(
                    record_ids,
                    reason,
                    organization_id=marker_organization_id,
                )
            )
        ),
        graph_adapter=graph_adapter,
        graph_summary_loader=graph_summary_loader,
    )
    return store.finalize_class_commentary_generation_execution_snapshot(
        int(generation["id"]),
        prompt_payload=built["prompt_payload"],
        memory_context=built["memory_context"],
    )


def process_class_commentary_batch_generation(
    generation_id: int,
    *,
    store=None,
    runtime_config: Optional[Mapping[str, object]] = None,
    generator=None,
    charge_finalizer=None,
    claim_owner: str = "",
    memory_service=None,
    graph_adapter=None,
    graph_summary_loader=None,
) -> dict:
    config = _runtime_config(runtime_config)
    target_store = _store(store)
    timeout = int(config.get("class_commentary_batch_generation_timeout") or 300)
    claimed = target_store.claim_class_commentary_batch_generation(
        int(generation_id),
        claim_owner=claim_owner or _claim_owner(),
        lease_seconds=max(60, 2 * timeout),
    )
    if not claimed:
        current = target_store.get_class_commentary_generation(int(generation_id))
        return {
            "status": "not_claimed",
            "generation_id": int(generation_id),
            "generation": current,
        }
    claim_token = str(claimed.get("batch_claim_token") or "")
    hold = target_store.get_class_commentary_generation_credit_hold(
        int(generation_id)
    )
    if not hold:
        target_store.release_class_commentary_batch_generation_claim(
            int(generation_id), claim_token=claim_token
        )
        raise ValueError("batch generation credit hold is missing")
    try:
        if str(claimed.get("execution_snapshot_status") or "") != "ready":
            claimed = _prepare_execution_snapshot(
                generation=claimed,
                store=target_store,
                config=config,
                memory_service=memory_service,
                graph_adapter=graph_adapter,
                graph_summary_loader=graph_summary_loader,
            )
        response = target_store.get_class_commentary_batch_generation_response(
            int(generation_id)
        )
        if response is None:
            if str(claimed.get("execution_snapshot_status") or "") != "ready":
                raise ValueError("batch generation execution snapshot is not ready")
            chat_request = _frozen_chat_request(claimed)
            local_request_id = (
                f"class-commentary-generation-{int(generation_id)}"
            )
            dispatch_status = str(
                claimed.get("batch_provider_dispatch_status") or "legacy_unknown"
            )
            if dispatch_status == "pending":
                claimed = (
                    target_store.mark_class_commentary_batch_provider_dispatch_started(
                        int(generation_id), claim_token=claim_token
                    )
                )
            elif dispatch_status in {"started", "legacy_unknown"}:
                provider_failure = build_provider_dispatch_interruption_snapshot(
                    local_request_id=local_request_id,
                    legacy=dispatch_status == "legacy_unknown",
                )
                error_code = str(provider_failure["error_code"])
                failed = target_store.fail_class_commentary_batch_generation_terminal(
                    int(generation_id),
                    claim_token=claim_token,
                    error_code=error_code,
                    provider_failure=provider_failure,
                )
                return {
                    "status": str(failed.get("status") or "failed"),
                    "generation_id": int(generation_id),
                    "error_code": error_code,
                    "provider_failure": provider_failure,
                }
            else:
                raise ValueError("batch provider dispatch status is invalid")
            try:
                provider_result = _call_generator(
                    generator, claimed, chat_request, config
                )
            except Exception as exc:
                provider_failure = build_provider_failure_snapshot(
                    exc,
                    local_request_id=local_request_id,
                )
                error_code = str(provider_failure["error_code"])
                logger.warning(
                    "class commentary provider call failed "
                    "generation_id=%s error_code=%s exception_type=%s "
                    "http_status=%s provider_request_id=%s result_state=%s",
                    int(generation_id),
                    error_code,
                    provider_failure["exception_type"],
                    provider_failure["http_status"],
                    provider_failure["provider_request_id"],
                    provider_failure["result_state"],
                )
                failed = target_store.fail_class_commentary_batch_generation_terminal(
                    int(generation_id),
                    claim_token=claim_token,
                    error_code=error_code,
                    provider_failure=provider_failure,
                )
                return {
                    "status": str(failed.get("status") or "failed"),
                    "generation_id": int(generation_id),
                    "error_code": error_code,
                    "provider_failure": provider_failure,
                }
            feedback_text, usage = _split_result(
                provider_result,
                provider=str(claimed.get("model_provider") or ""),
                model=str(claimed.get("model_name") or ""),
            )
            target_store.persist_class_commentary_batch_generation_response(
                int(generation_id),
                response_text=feedback_text,
                usage=usage,
                claim_token=claim_token,
            )
            response = target_store.get_class_commentary_batch_generation_response(
                int(generation_id)
            )
        if response is None:
            raise ValueError("batch generation response snapshot is missing")
        validated = target_store.validate_class_commentary_batch_generation_response(
            int(generation_id), claim_token=claim_token
        )
        hold = target_store.get_class_commentary_generation_credit_hold(
            int(generation_id)
        )
        if not hold:
            raise ValueError("batch generation credit hold is missing")
        if str(hold.get("status") or "") == "settled":
            charge_usage_id = int(hold.get("usage_id") or 0)
            if charge_usage_id <= 0:
                raise ValueError("settled batch generation hold has no usage")
        else:
            finalize = charge_finalizer or finalize_ai_charge
            charge = finalize(
                organization_id=int(claimed["organization_id"]),
                user_id=int(claimed["teacher_user_id"]),
                feature_key="class_commentary_generate",
                usage=response["usage"],
                source_record_type="class_commentary_generation",
                source_record_id=int(generation_id),
                request_id=str(hold["request_id"]),
                request_payload_hash=str(hold["request_payload_hash"]),
                credit_hold_generation_id=int(generation_id),
            )
            charge_usage_id = int(charge["id"])
        completed = target_store.complete_class_commentary_batch_generation(
            int(validated["id"]),
            charge_usage_id=charge_usage_id,
            claim_token=claim_token,
        )
        return {
            "status": str(completed.get("status") or "succeeded"),
            "generation_id": int(generation_id),
            "generation": completed,
        }
    except ClassCommentaryStructuredFeedbackValidationError as exc:
        error_code = str(exc.code or "structured_feedback_invalid")
        validation_failure = {
            "error_code": error_code,
            "student_id": exc.student_id,
            "field": str(exc.field or ""),
            "limit": exc.limit,
        }
        logger.warning(
            "class commentary batch validation failed "
            "generation_id=%s error_code=%s student_id=%s field=%s limit=%s",
            int(generation_id),
            error_code,
            exc.student_id,
            str(exc.field or ""),
            exc.limit,
        )
        failed = target_store.fail_class_commentary_batch_generation_validation(
            int(generation_id),
            claim_token=claim_token,
            error_code=error_code,
            validation_failure=validation_failure,
        )
        return {
            "status": str(failed.get("status") or "failed"),
            "generation_id": int(generation_id),
            "error_code": error_code,
            "validation_failure": validation_failure,
        }
    except CreditBalanceError:
        target_store.release_class_commentary_batch_generation_claim(
            int(generation_id), claim_token=claim_token
        )
        return {
            "status": "charge_pending",
            "generation_id": int(generation_id),
        }
    except Exception:
        target_store.release_class_commentary_batch_generation_claim(
            int(generation_id), claim_token=claim_token
        )
        raise
