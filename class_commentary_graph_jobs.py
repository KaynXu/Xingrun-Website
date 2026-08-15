from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from typing import Mapping, Optional

import ai_processor
import config_runtime
from class_commentary_learning_graph import (
    GRAPH_EVENT_SCHEMA_VERSION,
    LearningGraphSnapshotIntegrityError,
    content_hash,
    normalize_knowledge_point_alias,
)
from class_commentary_semantica import SemanticaGraphAdapter


_CANDIDATE_FIELDS = {
    "knowledge_point_key",
    "unmapped_candidate",
    "observed_state",
    "reported_trend",
    "evidence_quote",
    "teaching_methods",
    "next_steps",
    "teaching_method_causal_supported",
    "teaching_method_causal_evidence",
}

_CAUSAL_EVIDENCE_FIELDS = {
    "method_text",
    "evidence_quote",
}

_SERVER_EVIDENCE_FIELDS = {
    "evidence_start_offset",
    "evidence_end_offset",
    "evidence_content_hash",
}
_PERSISTED_CANDIDATE_FIELDS = _CANDIDATE_FIELDS | _SERVER_EVIDENCE_FIELDS
_PERSISTED_CAUSAL_EVIDENCE_FIELDS = (
    _CAUSAL_EVIDENCE_FIELDS | _SERVER_EVIDENCE_FIELDS
)
_EVIDENCE_SENTENCE_BOUNDARIES = "\n\r。！？!?；;"
_MIN_PRECISE_EVIDENCE_QUOTE_LENGTH = 4


def _server_evidence_span(
    evidence: Mapping[str, object], *, feedback_text: str
) -> tuple[str, int, int, str]:
    quote = str(evidence.get("evidence_quote") or "")
    if not quote.strip():
        raise ValueError("learning graph evidence quote is empty")
    positions = []
    cursor = 0
    while True:
        position = feedback_text.find(quote, cursor)
        if position < 0:
            break
        positions.append(position)
        cursor = position + max(1, len(quote))
    if not positions:
        raise ValueError("learning graph evidence quote does not match confirmed feedback")
    try:
        supplied_start = int(evidence.get("evidence_start_offset"))
    except (TypeError, ValueError):
        supplied_start = positions[0]
    start = min(positions, key=lambda position: (abs(position - supplied_start), position))
    end = start + len(quote)
    if len(quote.strip()) < _MIN_PRECISE_EVIDENCE_QUOTE_LENGTH:
        start = max(
            feedback_text.rfind(mark, 0, start)
            for mark in _EVIDENCE_SENTENCE_BOUNDARIES
        ) + 1
        right_boundaries = [
            position
            for mark in _EVIDENCE_SENTENCE_BOUNDARIES
            for position in [feedback_text.find(mark, end)]
            if position >= 0
        ]
        end = min(right_boundaries) + 1 if right_boundaries else len(feedback_text)
        while start < end and feedback_text[start].isspace():
            start += 1
        while end > start and feedback_text[end - 1].isspace():
            end -= 1
        quote = feedback_text[start:end]
    return quote, start, end, content_hash(quote)


def _runtime_config(runtime_config: Optional[Mapping[str, object]] = None) -> dict:
    return dict(runtime_config if runtime_config is not None else config_runtime.get_runtime_config())


def _enabled(config: Mapping[str, object]) -> bool:
    return config_runtime.normalize_bool_flag(config.get("class_commentary_graph_enabled"))


def _store(store=None):
    if store is not None:
        return store
    import class_commentary_learning_graph

    return class_commentary_learning_graph


def _rq_context() -> tuple[str, Optional[str]]:
    rq_job_id = None
    try:
        from rq import get_current_job

        job = get_current_job()
        rq_job_id = str(job.id) if job is not None else None
    except Exception:
        rq_job_id = None
    return f"{socket.gethostname()}:{os.getpid()}", rq_job_id


def _default_extractor(extraction_input: dict, config: Mapping[str, object]):
    job_timeout = max(
        60, int(config.get("class_commentary_graph_extraction_timeout") or 300)
    )
    request_timeout = float(
        config.get("class_commentary_graph_provider_timeout")
        or min(240, max(30, job_timeout - 30))
    )
    return ai_processor.extract_class_commentary_learning_events(
        extraction_input=extraction_input,
        provider=str(config.get("class_commentary_provider") or config.get("provider") or ""),
        model=str(config.get("class_commentary_model") or ""),
        openai_api_key=str(
            config.get("class_commentary_openai_api_key")
            or config.get("openai_api_key")
            or ""
        ),
        openai_base_url=str(
            config.get("class_commentary_openai_base_url")
            or config.get("openai_base_url")
            or ""
        ),
        openai_headers=str(config.get("class_commentary_openai_headers") or ""),
        request_timeout=request_timeout,
        max_retries=int(config.get("class_commentary_graph_provider_max_retries") or 0),
        include_usage=True,
    )


def _strict_candidates(payload: object, *, feedback_text: str) -> list[dict]:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    if not isinstance(payload, Mapping) or set(payload) != {"schema_version", "items"}:
        raise ValueError("learning graph extractor returned an invalid envelope")
    if str(payload.get("schema_version") or "") != GRAPH_EVENT_SCHEMA_VERSION:
        raise ValueError("learning graph extractor schema version mismatch")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("learning graph extractor items must be a list")
    candidates = []
    seen_item_keys = set()
    for raw_item in raw_items:
        if hasattr(raw_item, "model_dump"):
            raw_item = raw_item.model_dump(mode="json")
        raw_fields = set(raw_item) if isinstance(raw_item, Mapping) else set()
        if (
            not isinstance(raw_item, Mapping)
            or not _CANDIDATE_FIELDS.issubset(raw_fields)
            or not raw_fields.issubset(_PERSISTED_CANDIDATE_FIELDS)
        ):
            raise ValueError("learning graph extractor item contract mismatch")
        if not str(raw_item.get("evidence_quote") or "").strip():
            continue
        knowledge_point_key = raw_item.get("knowledge_point_key")
        unmapped_candidate = raw_item.get("unmapped_candidate")
        if bool(str(knowledge_point_key or "").strip()) == bool(
            str(unmapped_candidate or "").strip()
        ):
            raise ValueError("learning graph extractor must choose mapped or unmapped")
        if not isinstance(raw_item.get("teaching_methods"), list) or not isinstance(
            raw_item.get("next_steps"), list
        ):
            raise ValueError("learning graph extractor support lists are invalid")
        if not isinstance(raw_item.get("teaching_method_causal_supported"), bool):
            raise ValueError("learning graph extractor causal flag is invalid")
        causal_evidence = raw_item.get("teaching_method_causal_evidence")
        if not isinstance(causal_evidence, list) or any(
            not isinstance(item, Mapping)
            or not _CAUSAL_EVIDENCE_FIELDS.issubset(set(item))
            or not set(item).issubset(_PERSISTED_CAUSAL_EVIDENCE_FIELDS)
            for item in causal_evidence
        ):
            raise ValueError("learning graph extractor causal evidence is invalid")
        if not raw_item.get("teaching_method_causal_supported") and causal_evidence:
            raise ValueError("learning graph extractor causal evidence is inconsistent")
        normalized_item = dict(raw_item)
        quote, start, end, quote_hash = _server_evidence_span(
            normalized_item,
            feedback_text=feedback_text,
        )
        normalized_item["evidence_quote"] = quote
        normalized_item["evidence_start_offset"] = start
        normalized_item["evidence_end_offset"] = end
        normalized_item["evidence_content_hash"] = quote_hash
        normalized_item["teaching_method_causal_evidence"] = [
            {
                **dict(item),
                "evidence_quote": span[0],
                "evidence_start_offset": span[1],
                "evidence_end_offset": span[2],
                "evidence_content_hash": span[3],
            }
            for item in causal_evidence
            for span in [_server_evidence_span(item, feedback_text=feedback_text)]
        ]
        dedup_key = str(normalized_item.get("knowledge_point_key") or "").strip()
        if not dedup_key:
            dedup_key = "unmapped:" + normalize_knowledge_point_alias(
                str(normalized_item.get("unmapped_candidate") or "")
            )
        if not dedup_key:
            dedup_key = "quote:" + quote_hash
        if dedup_key in seen_item_keys:
            continue
        seen_item_keys.add(dedup_key)
        candidates.append(normalized_item)
    return candidates


def _adapter(config: Mapping[str, object], adapter=None):
    if adapter is not None:
        return adapter
    raw_path = str(config.get("class_commentary_graph_store_path") or "").strip()
    if not raw_path:
        raw_path = str(config_runtime.DEFAULTS["class_commentary_graph_store_path"])
    return SemanticaGraphAdapter(
        raw_path,
        timeout_seconds=int(
            config.get("class_commentary_graph_timeout")
            or config_runtime.DEFAULTS["class_commentary_graph_timeout"]
        ),
    )


def _extract_with_validation_correction(
    extract,
    per_student_input: dict,
    config: Mapping[str, object],
    *,
    feedback_text: str,
) -> tuple[list[dict], object, dict]:
    """调用提取器并过严格校验；校验失败时把错误回喂模型自纠一次。

    校验门禁保持 fail-closed 不变：自纠后的输出仍然必须完整通过校验。
    """
    result = extract(per_student_input, config)
    result_usage = {}
    if isinstance(result, tuple) and len(result) == 2:
        result, result_usage = result
    try:
        candidates = _strict_candidates(result, feedback_text=feedback_text)
        return candidates, result, result_usage
    except ValueError as validation_error:
        correction_input = dict(per_student_input)
        correction_input["correction"] = {
            "instruction": (
                "Your previous output failed server-side validation. "
                "Fix ONLY the violations described in validation_error and "
                "keep valid items unchanged."
            ),
            "validation_error": str(validation_error),
            "previous_output": result,
        }
        corrected = extract(correction_input, config)
        corrected_usage = {}
        if isinstance(corrected, tuple) and len(corrected) == 2:
            corrected, corrected_usage = corrected
        candidates = _strict_candidates(corrected, feedback_text=feedback_text)
        return candidates, corrected, corrected_usage or result_usage


def process_class_commentary_graph_extraction_job(
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
    owner, current_rq_job_id = _rq_context()
    claimed = target_store.claim_graph_extraction_job(
        int(job_id),
        claim_owner=claim_owner or owner,
        rq_job_id=rq_job_id or current_rq_job_id,
        lease_seconds=int(config.get("class_commentary_graph_extraction_timeout") or 300) * 2,
    )
    if not claimed:
        return {"enabled": True, "status": "not_claimed", "job_id": int(job_id)}
    token = str(claimed["claim_token"])
    try:
        frozen = target_store.get_graph_extraction_input(int(job_id))
        if not frozen or frozen.get("integrity_valid") is not True:
            target_store.mark_graph_extraction_integrity_failed(
                int(job_id), claim_token=token, error="immutable graph extraction input failed integrity"
            )
            return {"enabled": True, "status": "integrity_failed", "job_id": int(job_id)}
        extract = extractor or _default_extractor
        extraction_input_hash = str(frozen.get("extraction_input_hash") or "")
        student_items = list(frozen.get("student_feedback_items") or [])
        student_ids = [int(item["student_id"]) for item in student_items]
        student_id_set = set(student_ids)
        feedback_text_by_student = {
            int(item["student_id"]): str(item["feedback_text"])
            for item in student_items
        }
        if len(student_ids) != len(student_id_set):
            raise LearningGraphSnapshotIntegrityError(
                "graph extraction frozen student scope contains duplicates"
            )
        checkpoint_by_student = {}
        for checkpoint in target_store.list_graph_extraction_student_checkpoints(
            int(job_id), extraction_input_hash=extraction_input_hash
        ):
            student_id = int(checkpoint["student_id"])
            if student_id not in student_id_set:
                raise LearningGraphSnapshotIntegrityError(
                    "graph extraction checkpoint student is outside frozen scope"
                )
            try:
                checkpoint_candidates = _strict_candidates(
                    checkpoint["payload"],
                    feedback_text=feedback_text_by_student[student_id],
                )
            except ValueError as exc:
                raise LearningGraphSnapshotIntegrityError(
                    "graph extraction checkpoint candidate contract is invalid"
                ) from exc
            checkpoint_by_student[student_id] = {
                "candidates": checkpoint_candidates,
                "usage": dict(checkpoint.get("usage") or {}),
            }

        pending_student_item = next(
            (
                item
                for item in student_items
                if int(item["student_id"]) not in checkpoint_by_student
            ),
            None,
        )
        if pending_student_item is not None:
            per_student_input = {
                "feedback_text": str(pending_student_item["feedback_text"]),
                "subject_key": str(frozen.get("subject_key") or ""),
                "registry": (
                    frozen["model_registry"]
                    if "model_registry" in frozen
                    else frozen.get("registry") or []
                ),
            }
            checkpoint_candidates, _, result_usage = _extract_with_validation_correction(
                extract,
                per_student_input,
                config,
                feedback_text=str(pending_student_item["feedback_text"]),
            )
            normalized_usage = (
                dict(result_usage) if isinstance(result_usage, Mapping) else {}
            )
            student_id = int(pending_student_item["student_id"])
            target_store.save_graph_extraction_student_checkpoint(
                int(job_id),
                claim_token=token,
                student_id=student_id,
                extraction_input_hash=extraction_input_hash,
                payload={
                    "schema_version": GRAPH_EVENT_SCHEMA_VERSION,
                    "items": checkpoint_candidates,
                },
                usage=normalized_usage,
            )
            checkpoint_by_student[student_id] = {
                "candidates": checkpoint_candidates,
                "usage": normalized_usage,
            }

        if len(checkpoint_by_student) < len(student_items):
            continued = target_store.continue_graph_extraction_job(
                int(job_id),
                claim_token=token,
                completed_student_count=len(checkpoint_by_student),
                total_student_count=len(student_items),
            )
            if dispatcher is None:
                from class_commentary_graph_queue import (
                    dispatch_class_commentary_graph_work,
                )

                dispatcher = dispatch_class_commentary_graph_work
            try:
                dispatch = dispatcher(store=target_store, runtime_config=config)
            except Exception as exc:
                dispatch = {"queued": False, "error_type": exc.__class__.__name__}
            return {
                "enabled": True,
                "status": continued["status"],
                "job_id": int(job_id),
                "checkpointed_student_count": len(checkpoint_by_student),
                "student_count": len(student_items),
                "dispatch": dispatch,
            }

        candidates = []
        usage = []
        for student_item in student_items:
            student_id = int(student_item["student_id"])
            checkpoint = checkpoint_by_student[student_id]
            for candidate in checkpoint["candidates"]:
                scoped_candidate = dict(candidate)
                scoped_candidate["student_id"] = student_id
                candidates.append(scoped_candidate)
            usage.append(dict(checkpoint["usage"]))
        committed = target_store.commit_graph_extraction(
            int(job_id),
            claim_token=token,
            candidates_by_student=candidates,
            extractor_provider=str(config.get("class_commentary_provider") or config.get("provider") or ""),
            extractor_model=str(config.get("class_commentary_model") or ""),
            usage={"calls": usage},
            allow_active_organization_targets=True,
            require_model_eligible=True,
        )
    except LearningGraphSnapshotIntegrityError as exc:
        target_store.mark_graph_extraction_integrity_failed(
            int(job_id), claim_token=token, error=str(exc)
        )
        return {"enabled": True, "status": "integrity_failed", "job_id": int(job_id)}
    except Exception as exc:
        try:
            target_store.fail_graph_extraction_job(
                int(job_id),
                claim_token=token,
                error=f"{exc.__class__.__name__}: graph extraction failed",
            )
        except Exception:
            pass
        raise
    if dispatcher is None:
        from class_commentary_graph_queue import dispatch_class_commentary_graph_work

        dispatcher = dispatch_class_commentary_graph_work
    try:
        dispatch = dispatcher(store=target_store, runtime_config=config)
    except Exception as exc:
        dispatch = {"queued": False, "error_type": exc.__class__.__name__}
    return {
        "enabled": True,
        "status": committed["status"],
        "job_id": int(job_id),
        "event_ids": committed["event_ids"],
        "unmapped_candidate_ids": committed["unmapped_candidate_ids"],
        "dispatch": dispatch,
    }


def process_class_commentary_graph_sync_operation(
    operation_id: int,
    *,
    store=None,
    adapter=None,
    runtime_config: Optional[Mapping[str, object]] = None,
    claim_owner: Optional[str] = None,
    rq_job_id: Optional[str] = None,
) -> dict:
    config = _runtime_config(runtime_config)
    if not _enabled(config):
        return {"enabled": False, "status": "disabled", "operation_id": int(operation_id)}
    target_store = _store(store)
    owner, current_rq_job_id = _rq_context()
    claimed = target_store.claim_graph_sync_operation(
        int(operation_id),
        claim_owner=claim_owner or owner,
        rq_job_id=rq_job_id or current_rq_job_id,
        lease_seconds=int(config.get("class_commentary_graph_sync_timeout") or 120) * 2,
    )
    if not claimed:
        return {"enabled": True, "status": "not_claimed", "operation_id": int(operation_id)}
    token = str(claimed["claim_token"])
    try:
        frozen = target_store.get_graph_sync_payload(int(operation_id))
        if not frozen or frozen.get("integrity_valid") is not True:
            raise ValueError("graph sync payload failed integrity")
        curriculum_snapshot = (
            target_store.get_semantica_curriculum_snapshot()
            if hasattr(target_store, "get_semantica_curriculum_snapshot")
            else None
        )
        result = _adapter(config, adapter=adapter).apply_event(
            frozen["event"],
            curriculum_snapshot=curriculum_snapshot,
        )
        completed = target_store.complete_graph_sync_operation(
            int(operation_id), claim_token=token, result_snapshot=result
        )
    except Exception as exc:
        target_store.fail_graph_sync_operation(
            int(operation_id),
            claim_token=token,
            error=f"{exc.__class__.__name__}: graph sync failed",
        )
        raise
    return {"enabled": True, "status": completed["status"], "operation_id": int(operation_id)}


def run_class_commentary_graph_reconciliation(
    *,
    store=None,
    runtime_config: Optional[Mapping[str, object]] = None,
    dispatcher=None,
    scheduler=None,
    adapter=None,
) -> dict:
    config = _runtime_config(runtime_config)
    if not _enabled(config):
        return {"enabled": False, "status": "disabled"}
    target_store = _store(store)
    if dispatcher is None:
        from class_commentary_graph_queue import dispatch_class_commentary_graph_work

        dispatcher = dispatch_class_commentary_graph_work
    if scheduler is None:
        from class_commentary_graph_queue import ensure_class_commentary_graph_reconciliation_scheduled

        scheduler = ensure_class_commentary_graph_reconciliation_scheduled
    graph_adapter = _adapter(config, adapter=adapter)
    schedule = None
    try:
        graph_health = graph_adapter.health()
        derived_recovery = None
        if graph_health.get("error") in {"store_missing", "store_unreadable"}:
            derived_recovery = target_store.rebuild_semantica_graph(graph_adapter)
        reconciliation = target_store.reconcile_class_commentary_graph_store(
            limit=int(config.get("class_commentary_graph_reconcile_limit") or 100)
        )
        resumed_mappings = []
        mapping_failures = []
        if hasattr(target_store, "list_resumable_graph_mapping_actions") and hasattr(
            target_store, "resume_graph_mapping_action"
        ):
            for mapping in target_store.list_resumable_graph_mapping_actions(
                limit=int(config.get("class_commentary_graph_reconcile_limit") or 100)
            ):
                try:
                    resumed_mappings.append(
                        target_store.resume_graph_mapping_action(int(mapping["id"]))
                    )
                except Exception as exc:
                    mapping_failures.append(
                        {
                            "action_id": int(mapping["id"]),
                            "error": exc.__class__.__name__,
                        }
                    )
        reconciliation["resumed_mapping_count"] = len(resumed_mappings)
        reconciliation["mapping_failure_count"] = len(mapping_failures)
        if derived_recovery is None:
            trusted_events = target_store.list_trusted_graph_events()
            curriculum_snapshot = (
                target_store.get_semantica_curriculum_snapshot()
                if hasattr(target_store, "get_semantica_curriculum_snapshot")
                else None
            )
            expected_event_ids = {
                str(event["event_id"])
                for event in trusted_events
            }
            derived_event_ids = graph_adapter.trusted_learning_event_ids()
            if derived_event_ids != expected_event_ids:
                derived_recovery = target_store.rebuild_semantica_graph(graph_adapter)
                derived_recovery["reason"] = "trusted_event_set_mismatch"
                derived_recovery["missing_event_count"] = len(
                    expected_event_ids.difference(derived_event_ids)
                )
                derived_recovery["unknown_event_count"] = len(
                    derived_event_ids.difference(expected_event_ids)
                )
            elif graph_adapter.store_hash() != graph_adapter.expected_store_hash(
                trusted_events,
                curriculum_snapshot=curriculum_snapshot,
            ):
                derived_recovery = target_store.rebuild_semantica_graph(graph_adapter)
                derived_recovery["reason"] = "derived_store_hash_mismatch"
        dispatch = dispatcher(store=target_store, runtime_config=config)
    finally:
        schedule = scheduler(runtime_config=config, now=datetime.now(timezone.utc))
    return {
        "enabled": True,
        "status": "completed",
        "reconciliation": reconciliation,
        "derived_recovery": derived_recovery,
        "dispatch": dispatch,
        "schedule": schedule,
    }
