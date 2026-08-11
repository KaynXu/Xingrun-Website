from __future__ import annotations

import fcntl
import hashlib
import importlib.metadata
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Mapping, Optional


SEMANTICA_REQUIRED_VERSION = "0.6.0"
GRAPH_FORMAT_VERSION = "xingrun.class_commentary.semantica.v1"


class SemanticaGraphError(RuntimeError):
    pass


class SemanticaGraphUnavailableError(SemanticaGraphError):
    pass


class SemanticaGraphIntegrityError(SemanticaGraphError):
    pass


class SemanticaGraphScopeError(SemanticaGraphIntegrityError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(kind: str, *parts: object) -> str:
    digest = hashlib.sha256(_canonical_json([str(part) for part in parts]).encode()).hexdigest()
    return f"xr:{kind}:{digest}"


def _scope(properties: Mapping[str, object]) -> tuple[int, int, str]:
    try:
        organization_id = int(properties.get("organization_id"))
        student_id = int(properties.get("student_id"))
    except (TypeError, ValueError) as exc:
        raise SemanticaGraphScopeError("student graph object has invalid scope") from exc
    subject_key = str(properties.get("subject_key") or "").strip()
    if organization_id <= 0 or student_id <= 0 or not subject_key:
        raise SemanticaGraphScopeError("student graph object has incomplete scope")
    return organization_id, student_id, subject_key


class SemanticaGraphAdapter:
    """Xingrun-owned adapter around Semantica's local ContextGraph API."""

    def __init__(self, store_path: str | os.PathLike[str], *, timeout_seconds: int = 10):
        path = Path(store_path).expanduser()
        if not str(path).strip():
            raise ValueError("Semantica graph store path is required")
        self.store_path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.timeout_seconds = max(1, int(timeout_seconds))

    @staticmethod
    def _context_graph_class():
        try:
            installed = importlib.metadata.version("semantica")
        except importlib.metadata.PackageNotFoundError as exc:
            raise SemanticaGraphUnavailableError("semantica is not installed") from exc
        if installed != SEMANTICA_REQUIRED_VERSION:
            raise SemanticaGraphUnavailableError(
                f"semantica version mismatch: expected {SEMANTICA_REQUIRED_VERSION}, got {installed}"
            )
        from semantica.context import ContextGraph

        return ContextGraph

    def _new_graph(self):
        graph_class = self._context_graph_class()
        return graph_class(
            advanced_analytics=False,
            extract_entities=False,
            extract_relationships=False,
        )

    @contextmanager
    def _exclusive_lock(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+", encoding="utf-8")
        deadline = time.monotonic() + self.timeout_seconds
        try:
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise SemanticaGraphUnavailableError("Semantica graph store lock timed out") from exc
                    time.sleep(0.05)
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def _read_payload(self) -> dict:
        if not self.store_path.exists():
            return {"format_version": GRAPH_FORMAT_VERSION, "nodes": [], "edges": []}
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SemanticaGraphUnavailableError("Semantica graph store is unreadable") from exc
        if not isinstance(payload, dict):
            raise SemanticaGraphIntegrityError("Semantica graph store payload is invalid")
        if payload.get("format_version") != GRAPH_FORMAT_VERSION:
            raise SemanticaGraphIntegrityError("Semantica graph store format is unsupported")
        if not isinstance(payload.get("nodes"), list) or not isinstance(payload.get("edges"), list):
            raise SemanticaGraphIntegrityError("Semantica graph store collections are invalid")
        return payload

    def _canonicalize_with_semantica(self, nodes: Iterable[dict], edges: Iterable[dict]) -> dict:
        graph = self._new_graph()
        sorted_nodes = sorted(nodes, key=lambda item: str(item["id"]))
        sorted_edges = sorted(edges, key=lambda item: str(item["id"]))
        node_ids = {str(node["id"]) for node in sorted_nodes}
        for node in sorted_nodes:
            properties = dict(node.get("properties") or {})
            if not graph.add_node(
                str(node["id"]),
                str(node["type"]),
                content=str(node.get("content") or node["id"]),
                **properties,
            ):
                raise SemanticaGraphIntegrityError("Semantica rejected a graph node")
        for edge in sorted_edges:
            if str(edge["source"]) not in node_ids or str(edge["target"]) not in node_ids:
                raise SemanticaGraphIntegrityError("Semantica graph edge endpoint is missing")
            if not graph.add_edge(
                str(edge["source"]),
                str(edge["target"]),
                edge_type=str(edge["type"]),
                id=str(edge["id"]),
                **dict(edge.get("metadata") or {}),
            ):
                raise SemanticaGraphIntegrityError("Semantica rejected a graph edge")
        semantica_payload = graph.to_dict()
        if {str(node.get("id")) for node in semantica_payload.get("nodes", [])} != node_ids:
            raise SemanticaGraphIntegrityError("Semantica node round-trip mismatch")
        if {str(edge.get("id")) for edge in semantica_payload.get("edges", [])} != {
            str(edge["id"]) for edge in sorted_edges
        }:
            raise SemanticaGraphIntegrityError("Semantica edge round-trip mismatch")
        return {
            "format_version": GRAPH_FORMAT_VERSION,
            "semantica_version": SEMANTICA_REQUIRED_VERSION,
            "nodes": sorted(semantica_payload.get("nodes", []), key=lambda item: str(item["id"])),
            "edges": sorted(semantica_payload.get("edges", []), key=lambda item: str(item["id"])),
        }

    def _atomic_write(self, payload: Mapping[str, object]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            prefix=f".{self.store_path.name}.",
            suffix=".tmp",
            dir=str(self.store_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(_canonical_json(payload))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.store_path)
            directory_fd = os.open(self.store_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _event_graph(event: Mapping[str, object]) -> tuple[list[dict], list[dict]]:
        organization_id, student_id, subject_key = _scope(event)
        event_id = str(event.get("event_id") or "").strip()
        knowledge_point_key = str(event.get("knowledge_point_key") or "").strip()
        if not event_id or not knowledge_point_key:
            raise SemanticaGraphIntegrityError("trusted learning event identity is missing")
        scope = {
            "organization_id": organization_id,
            "student_id": student_id,
            "subject_key": subject_key,
        }
        # Every student-derived node is partitioned by the complete retrieval
        # scope. A class lesson or revision can contain several students, and a
        # student can have several subjects, so narrower IDs would let a later
        # event overwrite another scope's node properties.
        student_node = _stable_id("student", organization_id, student_id, subject_key)
        lesson_node = _stable_id(
            "lesson", organization_id, student_id, subject_key, event.get("lesson_id")
        )
        revision_node = _stable_id(
            "revision", organization_id, student_id, subject_key, event.get("revision_id")
        )
        kp_node = _stable_id("knowledge-point", organization_id, subject_key, knowledge_point_key)
        event_node = _stable_id("learning-event", event_id)
        state_node = _stable_id("learning-state", event_id, event.get("observed_state"))
        evidence_node = _stable_id("evidence", event.get("evidence_id"))

        nodes = [
            {"id": student_node, "type": "Student", "content": "Student", "properties": scope},
            {
                "id": lesson_node,
                "type": "Lesson",
                "content": str(event.get("lesson_name") or "Class feedback lesson"),
                "properties": {**scope, "lesson_id": int(event["lesson_id"])},
            },
            {
                "id": revision_node,
                "type": "ClassFeedbackRevision",
                "content": "Confirmed class feedback revision",
                "properties": {
                    **scope,
                    "revision_id": int(event["revision_id"]),
                    "revision_no": int(event.get("revision_no") or 0),
                    "confirmed_at": str(event.get("confirmed_at") or ""),
                },
            },
            {
                "id": kp_node,
                "type": "KnowledgePoint",
                "content": str(event.get("knowledge_point_name") or knowledge_point_key),
                "properties": {
                    "organization_id": organization_id,
                    "subject_key": subject_key,
                    "knowledge_point_key": knowledge_point_key,
                    "registry_version": int(event.get("registry_version") or 1),
                },
            },
            {
                "id": event_node,
                "type": "LearningEvent",
                "content": "Confirmed student learning observation",
                    "properties": {
                        **scope,
                        "event_id": event_id,
                        "observed_at": str(event.get("confirmed_at") or ""),
                        "desired_status": str(event.get("desired_status") or "active"),
                    },
            },
            {
                "id": state_node,
                "type": "LearningState",
                "content": str(event.get("observed_state") or "unknown"),
                "properties": {
                    **scope,
                    "event_id": event_id,
                    "state": str(event.get("observed_state") or "unknown"),
                    "reported_trend": str(event.get("reported_trend") or "new_observation"),
                    "observed_at": str(event.get("confirmed_at") or ""),
                    "desired_status": str(event.get("desired_status") or "active"),
                },
            },
            {
                "id": evidence_node,
                "type": "Evidence",
                "content": str(event.get("evidence_quote") or ""),
                "properties": {
                    **scope,
                    "evidence_id": str(event.get("evidence_id") or ""),
                    "content_hash": str(event.get("evidence_content_hash") or ""),
                    "start_offset": int(event.get("evidence_start_offset") or 0),
                    "end_offset": int(event.get("evidence_end_offset") or 0),
                },
            },
        ]

        def edge(source: str, target: str, edge_type: str, *identity: object) -> dict:
            return {
                "id": _stable_id("edge", edge_type, source, target, *identity),
                "source": source,
                "target": target,
                "type": edge_type,
                "metadata": {**scope, "event_id": event_id},
            }

        edges = [
            edge(event_node, lesson_node, "OBSERVED_IN", event_id),
            edge(event_node, kp_node, "ABOUT_KNOWLEDGE_POINT", event_id),
            edge(event_node, state_node, "HAS_STATE", event_id),
            edge(event_node, evidence_node, "SUPPORTED_BY", event_id),
            edge(evidence_node, revision_node, "FROM_REVISION", event_id),
            edge(revision_node, student_node, "FOR_STUDENT", event_id),
            edge(student_node, state_node, "HAS_STATE", event_id),
            edge(state_node, kp_node, "ABOUT_KNOWLEDGE_POINT", event_id),
        ]

        previous_event_id = str(event.get("previous_event_id") or "").strip()
        if previous_event_id:
            previous_state = _stable_id(
                "learning-state", previous_event_id, event.get("state_before")
            )
            edges.append(edge(state_node, previous_state, "SUPERSEDES", event_id))
            if bool(event.get("improved_from_trusted_state")):
                edges.append(edge(state_node, previous_state, "IMPROVED_FROM", event_id))

        supersedes_event_id = str(event.get("supersedes_event_id") or "").strip()
        if supersedes_event_id and supersedes_event_id != previous_event_id:
            supersedes_state = _stable_id(
                "learning-state", supersedes_event_id, event.get("supersedes_state")
            )
            edges.append(
                edge(state_node, supersedes_state, "SUPERSEDES", event_id, "correction")
            )

        for index, method in enumerate(event.get("teaching_methods") or []):
            if not isinstance(method, Mapping):
                continue
            method_text = str(method.get("text") or "").strip()
            if not method_text:
                continue
            method_node = _stable_id("teaching-method", event_id, index, method_text)
            nodes.append(
                {
                    "id": method_node,
                    "type": "TeachingMethod",
                    "content": method_text,
                    "properties": {**scope, "event_id": event_id},
                }
            )
            edges.append(edge(event_node, method_node, "TAUGHT_WITH", event_id, index))
            if bool(method.get("causal_supported")):
                edges.append(edge(method_node, state_node, "LED_TO", event_id, index))

        for index, next_step in enumerate(event.get("next_steps") or []):
            next_step_text = str(next_step.get("text") if isinstance(next_step, Mapping) else next_step).strip()
            if not next_step_text:
                continue
            next_node = _stable_id("next-step", event_id, index, next_step_text)
            nodes.append(
                {
                    "id": next_node,
                    "type": "NextStep",
                    "content": next_step_text,
                    "properties": {**scope, "event_id": event_id, "status": "confirmed"},
                }
            )
            edges.append(edge(event_node, next_node, "RECOMMENDS_NEXT", event_id, index))
        return nodes, edges

    def apply_event(self, event: Mapping[str, object]) -> dict:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            raise SemanticaGraphIntegrityError("trusted learning event identity is missing")
        desired_status = str(event.get("desired_status") or "")
        delete_event = desired_status == "deleted" or (
            desired_status == "superseded"
            and not str(event.get("superseded_by_event_id") or "").strip()
        )
        event_nodes, event_edges = ([], []) if delete_event else self._event_graph(event)
        with self._exclusive_lock():
            existing = self._read_payload()
            edges_by_id = {
                str(edge["id"]): dict(edge)
                for edge in existing["edges"]
                if str((edge.get("metadata") or {}).get("event_id") or "")
                != event_id
            }
            edges_by_id.update({str(edge["id"]): edge for edge in event_edges})
            referenced_node_ids = {
                str(endpoint)
                for edge in edges_by_id.values()
                for endpoint in (edge["source"], edge["target"])
            }
            nodes_by_id = {
                str(node["id"]): dict(node)
                for node in existing["nodes"]
                if str(node["id"]) in referenced_node_ids
            }
            nodes_by_id.update({str(node["id"]): node for node in event_nodes})
            payload = self._canonicalize_with_semantica(nodes_by_id.values(), edges_by_id.values())
            self._atomic_write(payload)
        return {
            "event_id": event_id,
            "deleted": delete_event,
            "node_count": len(payload["nodes"]),
            "edge_count": len(payload["edges"]),
            "store_hash": hashlib.sha256(_canonical_json(payload).encode()).hexdigest(),
        }

    def rebuild(self, events: Iterable[Mapping[str, object]]) -> dict:
        nodes_by_id: dict[str, dict] = {}
        edges_by_id: dict[str, dict] = {}
        event_count = 0
        for event in events:
            event_nodes, event_edges = self._event_graph(event)
            nodes_by_id.update({str(node["id"]): node for node in event_nodes})
            edges_by_id.update({str(edge["id"]): edge for edge in event_edges})
            event_count += 1
        payload = self._canonicalize_with_semantica(nodes_by_id.values(), edges_by_id.values())
        with self._exclusive_lock():
            self._atomic_write(payload)
        return {
            "event_count": event_count,
            "node_count": len(payload["nodes"]),
            "edge_count": len(payload["edges"]),
            "store_hash": hashlib.sha256(_canonical_json(payload).encode()).hexdigest(),
        }

    @staticmethod
    def _trusted_learning_event_ids_from_payload(payload: Mapping[str, object]) -> set[str]:
        node_ids = set()
        learning_event_ids = set()
        for node in payload.get("nodes") or []:
            if not isinstance(node, Mapping):
                raise SemanticaGraphIntegrityError("Semantica graph node is invalid")
            node_id = str(node.get("id") or "").strip()
            if not node_id or node_id in node_ids:
                raise SemanticaGraphIntegrityError("Semantica graph node identity is invalid")
            node_ids.add(node_id)
            if str(node.get("type") or "") != "LearningEvent":
                continue
            properties = dict(node.get("properties") or node.get("metadata") or {})
            _scope(properties)
            event_id = str(properties.get("event_id") or "").strip()
            if not event_id or node_id != _stable_id("learning-event", event_id):
                raise SemanticaGraphIntegrityError(
                    "Semantica trusted learning event identity is invalid"
                )
            if event_id in learning_event_ids:
                raise SemanticaGraphIntegrityError(
                    "Semantica trusted learning event identity is duplicated"
                )
            learning_event_ids.add(event_id)
        edge_ids = set()
        for edge in payload.get("edges") or []:
            if not isinstance(edge, Mapping):
                raise SemanticaGraphIntegrityError("Semantica graph edge is invalid")
            edge_id = str(edge.get("id") or "").strip()
            if not edge_id or edge_id in edge_ids:
                raise SemanticaGraphIntegrityError("Semantica graph edge identity is invalid")
            edge_ids.add(edge_id)
            if (
                str(edge.get("source") or "") not in node_ids
                or str(edge.get("target") or "") not in node_ids
            ):
                raise SemanticaGraphIntegrityError(
                    "Semantica graph edge endpoint is missing"
                )
        return learning_event_ids

    def trusted_learning_event_ids(self) -> set[str]:
        return self._trusted_learning_event_ids_from_payload(self._read_payload())

    def scoped_snapshot(self, *, organization_id: int, student_id: int, subject_key: str) -> dict:
        expected = (int(organization_id), int(student_id), str(subject_key).strip())
        if not self.store_path.exists():
            raise SemanticaGraphUnavailableError("Semantica graph store is missing")
        payload = self._read_payload()
        nodes_by_id = {
            str(node.get("id") or ""): dict(node)
            for node in payload["nodes"]
            if str(node.get("id") or "")
        }
        node_ids = set()
        edges = []
        for raw_edge in payload["edges"]:
            edge = dict(raw_edge)
            if _scope(dict(edge.get("metadata") or {})) != expected:
                continue
            source_id = str(edge.get("source") or "")
            target_id = str(edge.get("target") or "")
            endpoints = [nodes_by_id.get(source_id), nodes_by_id.get(target_id)]
            if any(node is None for node in endpoints):
                raise SemanticaGraphScopeError("Semantica scoped edge endpoint is missing")
            for node in endpoints:
                properties = dict(node.get("properties") or node.get("metadata") or {})
                if str(node.get("type") or "") == "KnowledgePoint":
                    if (
                        int(properties.get("organization_id") or 0) != expected[0]
                        or str(properties.get("subject_key") or "") != expected[2]
                    ):
                        raise SemanticaGraphScopeError("Semantica knowledge point scope mismatch")
                elif _scope(properties) != expected:
                    raise SemanticaGraphScopeError("Semantica node scope mismatch")
            node_ids.update((source_id, target_id))
            edges.append(edge)
        nodes = [nodes_by_id[node_id] for node_id in node_ids]
        snapshot = {
            "organization_id": expected[0],
            "student_id": expected[1],
            "subject_key": expected[2],
            "nodes": sorted(nodes, key=lambda item: str(item.get("id") or "")),
            "edges": sorted(edges, key=lambda item: str(item.get("id") or "")),
        }
        snapshot["hash"] = hashlib.sha256(_canonical_json(snapshot).encode()).hexdigest()
        return snapshot

    def health(self) -> dict:
        if not self.store_path.exists():
            return {"healthy": False, "error": "store_missing"}
        try:
            self._context_graph_class()
        except SemanticaGraphUnavailableError:
            raise
        try:
            payload = self._read_payload()
            event_ids = self._trusted_learning_event_ids_from_payload(payload)
        except (SemanticaGraphError, OSError, TypeError, ValueError):
            return {"healthy": False, "error": "store_unreadable"}
        return {
            "healthy": True,
            "semantica_version": SEMANTICA_REQUIRED_VERSION,
            "node_count": len(payload["nodes"]),
            "edge_count": len(payload["edges"]),
            "event_count": len(event_ids),
        }
