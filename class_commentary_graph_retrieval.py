from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Callable, Optional

import config_runtime
from class_commentary_learning_graph import canonical_json, content_hash
from class_commentary_semantica import (
    SemanticaGraphAdapter,
    SemanticaGraphError,
    SemanticaGraphScopeError,
    SemanticaGraphUnavailableError,
)


GRAPH_CONTEXT_SCHEMA_VERSION = "class_commentary.student_graph_context.v1"


class ClassCommentaryStudentGraphRetrievalError(RuntimeError):
    pass


def build_student_graph_query(
    *, organization_id: int, student_id: int, subject_key: str
) -> dict:
    organization_id = int(organization_id)
    student_id = int(student_id)
    subject_key = str(subject_key or "").strip()
    if organization_id <= 0 or student_id <= 0 or not subject_key:
        raise ClassCommentaryStudentGraphRetrievalError("graph_scope_invalid")
    return {
        "organization_id": organization_id,
        "student_id": student_id,
        "subject_key": subject_key,
    }


def empty_isolated_student_graph_context(
    *, organization_id: int, student_id: int, subject_key: str, retrieval_status: str
) -> dict:
    context = {
        "schema_version": GRAPH_CONTEXT_SCHEMA_VERSION,
        "organization_id": int(organization_id),
        "student_id": int(student_id),
        "subject_key": str(subject_key),
        "retrieval_status": str(retrieval_status),
        "current_states": [],
        "recent_changes": [],
        "allowed_evidence_refs": [],
        "semantica_snapshot_hash": "",
    }
    return {**context, "snapshot_hash": content_hash(canonical_json(context))}


def _adapter(config: Mapping[str, object]):
    store_path = str(config.get("class_commentary_graph_store_path") or "").strip()
    if not store_path:
        store_path = str(
            Path(__file__).resolve().parent
            / "data"
            / "class_commentary_semantica_graph.json"
        )
    return SemanticaGraphAdapter(
        store_path,
        timeout_seconds=int(config.get("class_commentary_graph_timeout") or 10),
    )


def _summary_loader(
    *, organization_id: int, task_id: int, student_id: int, subject_key: str
) -> dict:
    from class_commentary_learning_graph import get_student_learning_graph_summary

    return get_student_learning_graph_summary(
        organization_id=organization_id,
        task_id=task_id,
        student_id=student_id,
        subject_key=subject_key,
        event_limit=100,
    )


def _bounded_context(
    summary: Mapping[str, object],
    *,
    scope: Mapping[str, object],
    semantica_hash: str,
    event_limit: int,
    char_limit: int,
    token_limit: int,
) -> dict:
    bounded_event_limit = max(1, int(event_limit))
    bounded_char_limit = max(256, int(char_limit))
    bounded_token_limit = max(512, int(token_limit))

    def clipped(value: object, limit: int) -> str:
        return str(value or "")[: max(0, int(limit))]

    def within_budget(states: list[dict], changes: list[dict], refs: list[str]) -> bool:
        candidate = {
            "schema_version": GRAPH_CONTEXT_SCHEMA_VERSION,
            **dict(scope),
            "retrieval_status": "ready" if changes or states else "empty",
            "current_states": states,
            "recent_changes": changes,
            "allowed_evidence_refs": sorted(set(refs)),
            "semantica_snapshot_hash": str(semantica_hash),
            "snapshot_hash": "0" * 64,
        }
        # UTF-8 bytes are a conservative upper bound for tokenizer pieces and
        # keep the limit provider-independent.
        return len(canonical_json(candidate).encode("utf-8")) <= bounded_token_limit

    current_states: list[dict] = []
    raw_current_states = [
        item for item in summary.get("current_states") or [] if isinstance(item, Mapping)
    ]
    raw_current_states.sort(
        key=lambda item: (
            str(item.get("knowledge_point_key") or ""),
            str(item.get("observed_at") or ""),
        )
    )
    for item in raw_current_states[: min(bounded_event_limit, 8)]:
        curriculum = item.get("curriculum") if isinstance(item.get("curriculum"), Mapping) else {}
        state = {
            "knowledge_point_key": clipped(item.get("knowledge_point_key"), 160),
            "knowledge_point_name": clipped(item.get("knowledge_point_name"), 160),
            "state": clipped(item.get("state") or "unknown", 32),
            "observed_at": clipped(item.get("observed_at"), 64),
            "curriculum": {
                "path": [
                    {
                        "node_type": clipped(path_item.get("node_type"), 32),
                        "name": clipped(path_item.get("name"), 120),
                    }
                    for path_item in list(curriculum.get("path") or [])[:6]
                    if isinstance(path_item, Mapping)
                ],
                "prerequisites": [
                    {
                        "knowledge_point_key": clipped(related.get("node_key"), 160),
                        "name": clipped(related.get("canonical_name"), 120),
                    }
                    for related in list(curriculum.get("prerequisites") or [])[:4]
                    if isinstance(related, Mapping)
                ],
                "follow_ups": [
                    {
                        "knowledge_point_key": clipped(related.get("node_key"), 160),
                        "name": clipped(related.get("canonical_name"), 120),
                    }
                    for related in list(curriculum.get("follow_ups") or [])[:4]
                    if isinstance(related, Mapping)
                ],
                "source_revision": clipped(
                    (curriculum.get("source") or {}).get("dataset_revision")
                    if isinstance(curriculum.get("source"), Mapping)
                    else "",
                    64,
                ),
            },
        }
        if not curriculum:
            state.pop("curriculum", None)
        if within_budget([*current_states, state], [], []):
            current_states.append(state)
        else:
            break
    changes: list[dict] = []
    used_chars = 0
    allowed_refs: list[str] = []
    timeline = [item for item in summary.get("timeline") or [] if isinstance(item, Mapping)]
    timeline.sort(
        key=lambda item: (str(item.get("observed_at") or ""), str(item.get("event_ref") or "")),
        reverse=True,
    )
    for item in timeline[:bounded_event_limit]:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), Mapping) else {}
        quote = clipped(evidence.get("quote"), bounded_char_limit)
        if used_chars + len(quote) > bounded_char_limit:
            remaining = max(0, bounded_char_limit - used_chars)
            quote = quote[:remaining]
        evidence_ref = clipped(evidence.get("evidence_ref"), 160)
        curriculum = item.get("curriculum") if isinstance(item.get("curriculum"), Mapping) else {}
        change = {
            "event_ref": clipped(item.get("event_ref"), 160),
            "knowledge_point_key": clipped(item.get("knowledge_point_key"), 160),
            "knowledge_point_name": clipped(item.get("knowledge_point_name"), 160),
            "state": clipped(item.get("state") or "unknown", 32),
            "previous_state": (
                clipped(item.get("previous_state"), 32)
                if item.get("previous_state") is not None
                else None
            ),
            "trend": clipped(item.get("trend") or "new_observation", 32),
            "observed_at": clipped(item.get("observed_at"), 64),
            "evidence": {
                "evidence_ref": evidence_ref,
                "quote": quote,
                "lesson_id": int(evidence.get("lesson_id") or 0),
                "revision_id": int(evidence.get("revision_id") or 0),
                "confirmed_at": clipped(evidence.get("confirmed_at"), 64),
            },
            "teaching_methods": [
                clipped(value, 240) for value in list(item.get("teaching_methods") or [])[:4]
            ],
            "next_steps": [
                clipped(value, 240) for value in list(item.get("next_steps") or [])[:4]
            ],
            "curriculum": {
                "path": [
                    clipped(path_item.get("name"), 120)
                    for path_item in list(curriculum.get("path") or [])[:6]
                    if isinstance(path_item, Mapping)
                ],
                "prerequisites": [
                    clipped(related.get("canonical_name"), 120)
                    for related in list(curriculum.get("prerequisites") or [])[:4]
                    if isinstance(related, Mapping)
                ],
                "follow_ups": [
                    clipped(related.get("canonical_name"), 120)
                    for related in list(curriculum.get("follow_ups") or [])[:4]
                    if isinstance(related, Mapping)
                ],
            },
        }
        if not curriculum:
            change.pop("curriculum", None)
        next_refs = [*allowed_refs, evidence_ref] if evidence_ref else list(allowed_refs)
        if within_budget(current_states, [*changes, change], next_refs):
            changes.append(change)
            allowed_refs = next_refs
            used_chars += len(quote)
        else:
            break
    context = {
        "schema_version": GRAPH_CONTEXT_SCHEMA_VERSION,
        **dict(scope),
        "retrieval_status": "ready" if changes or current_states else "empty",
        "current_states": current_states,
        "recent_changes": changes,
        "allowed_evidence_refs": sorted(set(allowed_refs)),
        "semantica_snapshot_hash": str(semantica_hash),
    }
    return {**context, "snapshot_hash": content_hash(canonical_json(context))}


def retrieve_isolated_student_graph_context(
    *,
    generation: Mapping[str, object],
    student_id: int,
    class_context: Mapping[str, object],
    runtime_config: Optional[Mapping[str, object]] = None,
    graph_adapter=None,
    summary_loader: Optional[Callable[..., dict]] = None,
    require_available: bool = False,
) -> dict:
    config = dict(
        runtime_config if runtime_config is not None else config_runtime.get_runtime_config()
    )
    scope = build_student_graph_query(
        organization_id=int(generation.get("organization_id") or 0),
        student_id=int(student_id),
        subject_key=str(class_context.get("subject_key") or ""),
    )
    if not config_runtime.normalize_bool_flag(config.get("class_commentary_graph_enabled")):
        if require_available:
            raise ClassCommentaryStudentGraphRetrievalError("graph_disabled")
        return empty_isolated_student_graph_context(
            **scope, retrieval_status="disabled"
        )
    try:
        semantica_snapshot = (graph_adapter or _adapter(config)).scoped_snapshot(**scope)
        if any(semantica_snapshot.get(key) != value for key, value in scope.items()):
            raise ClassCommentaryStudentGraphRetrievalError("graph_scope_mismatch")
        if require_available and not str(semantica_snapshot.get("hash") or ""):
            raise ClassCommentaryStudentGraphRetrievalError(
                "graph_snapshot_invalid"
            )
        summary = (summary_loader or _summary_loader)(
            organization_id=scope["organization_id"],
            task_id=int(generation.get("task_id") or 0),
            student_id=scope["student_id"],
            subject_key=scope["subject_key"],
        )
        if any(summary.get(key) != value for key, value in scope.items()):
            raise ClassCommentaryStudentGraphRetrievalError("graph_scope_mismatch")
    except ClassCommentaryStudentGraphRetrievalError:
        raise
    except SemanticaGraphScopeError as exc:
        raise ClassCommentaryStudentGraphRetrievalError("graph_scope_mismatch") from exc
    except (OSError, SemanticaGraphUnavailableError) as exc:
        if require_available:
            raise ClassCommentaryStudentGraphRetrievalError(
                "graph_unavailable"
            ) from exc
        return empty_isolated_student_graph_context(
            **scope, retrieval_status="degraded"
        )
    except SemanticaGraphError as exc:
        raise ClassCommentaryStudentGraphRetrievalError(
            "graph_integrity_failed"
        ) from exc
    except Exception as exc:
        raise ClassCommentaryStudentGraphRetrievalError("graph_retrieval_failed") from exc
    return _bounded_context(
        summary,
        scope=scope,
        semantica_hash=str(semantica_snapshot.get("hash") or ""),
        event_limit=int(config.get("class_commentary_graph_retrieval_event_limit") or 12),
        char_limit=int(config.get("class_commentary_graph_retrieval_char_limit") or 4000),
        token_limit=int(config.get("class_commentary_graph_retrieval_token_limit") or 8000),
    )


def validate_isolated_student_graph_context_snapshot(
    *,
    generation: Mapping[str, object],
    student_id: int,
    graph_context: Mapping[str, object],
    class_context: Mapping[str, object],
    summary_loader: Optional[Callable[..., dict]] = None,
    runtime_config: Optional[Mapping[str, object]] = None,
    graph_adapter=None,
    revalidate_semantica: bool = False,
    require_available: bool = False,
) -> None:
    scope = build_student_graph_query(
        organization_id=int(generation.get("organization_id") or 0),
        student_id=int(student_id),
        subject_key=str(class_context.get("subject_key") or ""),
    )
    if str(graph_context.get("schema_version") or "") != GRAPH_CONTEXT_SCHEMA_VERSION:
        raise ClassCommentaryStudentGraphRetrievalError("graph_snapshot_invalid")
    if any(graph_context.get(key) != value for key, value in scope.items()):
        raise ClassCommentaryStudentGraphRetrievalError("graph_scope_mismatch")
    retrieval_status = str(graph_context.get("retrieval_status") or "")
    semantica_snapshot_hash = str(
        graph_context.get("semantica_snapshot_hash") or ""
    )
    if require_available:
        config = dict(
            runtime_config
            if runtime_config is not None
            else config_runtime.get_runtime_config()
        )
        if (
            not config_runtime.normalize_bool_flag(
                config.get("class_commentary_graph_enabled")
            )
            or retrieval_status not in {"ready", "empty"}
            or not semantica_snapshot_hash
        ):
            raise ClassCommentaryStudentGraphRetrievalError(
                "graph_snapshot_unavailable"
            )
    snapshot_without_hash = {
        key: value for key, value in graph_context.items() if key != "snapshot_hash"
    }
    if content_hash(canonical_json(snapshot_without_hash)) != str(
        graph_context.get("snapshot_hash") or ""
    ):
        raise ClassCommentaryStudentGraphRetrievalError("graph_snapshot_invalid")
    allowed_refs = graph_context.get("allowed_evidence_refs")
    if not isinstance(allowed_refs, list) or any(
        not isinstance(value, str) or not value for value in allowed_refs
    ):
        raise ClassCommentaryStudentGraphRetrievalError("graph_snapshot_invalid")
    if revalidate_semantica and semantica_snapshot_hash:
        config = dict(
            runtime_config
            if runtime_config is not None
            else config_runtime.get_runtime_config()
        )
        try:
            current_semantica = (graph_adapter or _adapter(config)).scoped_snapshot(
                **scope
            )
        except SemanticaGraphScopeError as exc:
            raise ClassCommentaryStudentGraphRetrievalError(
                "graph_scope_mismatch"
            ) from exc
        except (OSError, SemanticaGraphUnavailableError) as exc:
            raise ClassCommentaryStudentGraphRetrievalError(
                "graph_snapshot_unavailable"
            ) from exc
        except SemanticaGraphError as exc:
            raise ClassCommentaryStudentGraphRetrievalError(
                "graph_integrity_failed"
            ) from exc
        if (
            any(current_semantica.get(key) != value for key, value in scope.items())
            or str(current_semantica.get("hash") or "")
            != semantica_snapshot_hash
        ):
            raise ClassCommentaryStudentGraphRetrievalError(
                "graph_snapshot_stale"
            )
    if not allowed_refs:
        return
    summary = (summary_loader or _summary_loader)(
        organization_id=scope["organization_id"],
        task_id=int(generation.get("task_id") or 0),
        student_id=scope["student_id"],
        subject_key=scope["subject_key"],
    )
    current_refs = {
        str(item.get("evidence", {}).get("evidence_ref") or "")
        for item in summary.get("timeline") or []
        if isinstance(item, Mapping) and isinstance(item.get("evidence"), Mapping)
    }
    if not set(allowed_refs).issubset(current_refs):
        raise ClassCommentaryStudentGraphRetrievalError("graph_snapshot_stale")


def validate_used_graph_evidence_refs(
    used_refs: object, *, allowed_refs: object
) -> list[str]:
    if not isinstance(used_refs, list) or not isinstance(allowed_refs, list):
        raise ClassCommentaryStudentGraphRetrievalError("graph_evidence_refs_invalid")
    if any(not isinstance(value, str) or not value for value in used_refs):
        raise ClassCommentaryStudentGraphRetrievalError("graph_evidence_refs_invalid")
    normalized = list(dict.fromkeys(used_refs))
    if not set(normalized).issubset(set(allowed_refs)):
        raise ClassCommentaryStudentGraphRetrievalError("graph_evidence_refs_invalid")
    return normalized
