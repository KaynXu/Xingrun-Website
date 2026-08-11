from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

import ai_processor
import config_runtime
from class_commentary_learning_graph import GRAPH_EVENT_SCHEMA_VERSION
from class_commentary_semantica import SemanticaGraphAdapter


_CANDIDATE_FIELDS = {
    "knowledge_point_key",
    "unmapped_candidate",
    "observed_state",
    "reported_trend",
    "evidence_quote",
    "evidence_start_offset",
    "evidence_end_offset",
    "evidence_content_hash",
    "teaching_methods",
    "next_steps",
    "teaching_method_causal_supported",
    "teaching_method_causal_evidence",
}

_CAUSAL_EVIDENCE_FIELDS = {
    "method_text",
    "evidence_quote",
    "evidence_start_offset",
    "evidence_end_offset",
    "evidence_content_hash",
}


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
        include_usage=True,
    )


def _strict_candidates(payload: object) -> list[dict]:
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
    for raw_item in raw_items:
        if hasattr(raw_item, "model_dump"):
            raw_item = raw_item.model_dump(mode="json")
        if not isinstance(raw_item, Mapping) or set(raw_item) != _CANDIDATE_FIELDS:
            raise ValueError("learning graph extractor item contract mismatch")
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
            not isinstance(item, Mapping) or set(item) != _CAUSAL_EVIDENCE_FIELDS
            for item in causal_evidence
        ):
            raise ValueError("learning graph extractor causal evidence is invalid")
        if not raw_item.get("teaching_method_causal_supported") and causal_evidence:
            raise ValueError("learning graph extractor causal evidence is inconsistent")
        candidates.append(dict(raw_item))
    return candidates


def _adapter(config: Mapping[str, object], adapter=None):
    if adapter is not None:
        return adapter
    raw_path = str(config.get("class_commentary_graph_store_path") or "").strip()
    if not raw_path:
        base_dir = Path(__file__).resolve().parent
        raw_path = str(base_dir / "data" / "class_commentary_semantica_graph.json")
    return SemanticaGraphAdapter(
        raw_path,
        timeout_seconds=int(config.get("class_commentary_graph_timeout") or 10),
    )


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
        candidates = []
        usage = []
        for student_item in frozen.get("student_feedback_items") or []:
            per_student_input = {
                "feedback_text": str(student_item["feedback_text"]),
                "subject_key": str(frozen.get("subject_key") or ""),
                "registry": frozen.get("registry") or [],
            }
            result = extract(per_student_input, config)
            result_usage = {}
            if isinstance(result, tuple) and len(result) == 2:
                result, result_usage = result
            for candidate in _strict_candidates(result):
                candidate["student_id"] = int(student_item["student_id"])
                candidates.append(candidate)
            if isinstance(result_usage, Mapping):
                usage.append(dict(result_usage))
        committed = target_store.commit_graph_extraction(
            int(job_id),
            claim_token=token,
            candidates_by_student=candidates,
            extractor_provider=str(config.get("class_commentary_provider") or config.get("provider") or ""),
            extractor_model=str(config.get("class_commentary_model") or ""),
            usage={"calls": usage},
        )
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
        result = _adapter(config, adapter=adapter).apply_event(frozen["event"])
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
        if derived_recovery is None:
            expected_event_ids = {
                str(event["event_id"])
                for event in target_store.list_trusted_graph_events()
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
