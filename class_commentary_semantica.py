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
    def _installed_version() -> str:
        try:
            installed = importlib.metadata.version("semantica")
        except importlib.metadata.PackageNotFoundError as exc:
            raise SemanticaGraphUnavailableError("semantica is not installed") from exc
        if installed != SEMANTICA_REQUIRED_VERSION:
            raise SemanticaGraphUnavailableError(
                f"semantica version mismatch: expected {SEMANTICA_REQUIRED_VERSION}, got {installed}"
            )
        return installed

    @classmethod
    def _context_graph_class(cls):
        cls._installed_version()
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
    def _merge_node(existing: Mapping[str, object], incoming: Mapping[str, object]) -> dict:
        if str(existing.get("id") or "") != str(incoming.get("id") or ""):
            raise SemanticaGraphIntegrityError("cannot merge different graph nodes")
        if str(existing.get("type") or "") != str(incoming.get("type") or ""):
            raise SemanticaGraphIntegrityError("graph node type changed for a stable identity")
        properties = dict(existing.get("properties") or existing.get("metadata") or {})
        for key, value in dict(incoming.get("properties") or {}).items():
            previous = properties.get(key)
            if previous not in (None, "", 0) and value not in (None, "", 0) and previous != value:
                raise SemanticaGraphIntegrityError(
                    f"graph node property changed for a stable identity: {key}"
                )
            if value not in (None, "", 0) or key not in properties:
                properties[key] = value
        return {
            "id": str(incoming["id"]),
            "type": str(incoming["type"]),
            "content": str(incoming.get("content") or existing.get("content") or incoming["id"]),
            "properties": properties,
        }

    @classmethod
    def _upsert_nodes(cls, target: dict[str, dict], nodes: Iterable[Mapping[str, object]]) -> None:
        for node in nodes:
            node_id = str(node.get("id") or "")
            if not node_id:
                raise SemanticaGraphIntegrityError("graph node identity is missing")
            existing = target.get(node_id)
            target[node_id] = cls._merge_node(existing, node) if existing else dict(node)

    @staticmethod
    def _curriculum_graph(
        snapshot: Optional[Mapping[str, object]],
    ) -> tuple[list[dict], list[dict]]:
        if not snapshot:
            return [], []
        if str(snapshot.get("schema_version") or "") != "xingrun.semantica-curriculum.v1":
            raise SemanticaGraphIntegrityError("curriculum graph snapshot schema is invalid")
        raw_nodes = snapshot.get("nodes")
        raw_edges = snapshot.get("edges")
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise SemanticaGraphIntegrityError("curriculum graph snapshot is invalid")
        nodes = []
        known = set()
        for raw in raw_nodes:
            if not isinstance(raw, Mapping):
                raise SemanticaGraphIntegrityError("curriculum graph node is invalid")
            package_key = str(raw.get("package_key") or "").strip()
            version_key = str(raw.get("version_key") or "").strip()
            node_key = str(raw.get("node_key") or "").strip()
            subject_key = str(raw.get("subject_key") or "").strip()
            node_type = str(raw.get("node_type") or "").strip()
            if not all((package_key, version_key, node_key, subject_key, node_type)):
                raise SemanticaGraphIntegrityError("curriculum graph node identity is missing")
            node_id = _stable_id("curriculum-base", package_key, version_key, node_key)
            if node_id in known:
                raise SemanticaGraphIntegrityError("curriculum graph node is duplicated")
            known.add(node_id)
            nodes.append(
                {
                    "id": node_id,
                    "type": "KnowledgePoint" if node_type in {"Concept", "Skill"} else node_type,
                    "content": str(raw.get("canonical_name") or node_key),
                    "properties": {
                        "scope_type": "curriculum",
                        "package_key": package_key,
                        "version_key": version_key,
                        "version_status": str(raw.get("version_status") or ""),
                        "subject_key": subject_key,
                        "node_key": node_key,
                        "curriculum_node_type": node_type,
                        "knowledge_point_kind": str(raw.get("knowledge_point_kind") or ""),
                        "source_revision": str(raw.get("source_revision") or ""),
                        "source_sha256": str(raw.get("source_sha256") or ""),
                        "curriculum_content_hash": str(raw.get("curriculum_content_hash") or ""),
                        "description": str(raw.get("description") or ""),
                        "importance": str(raw.get("importance") or ""),
                        "stage_key": str(raw.get("stage_key") or ""),
                        "grade_key": str(raw.get("grade_key") or ""),
                        "semester_key": str(raw.get("semester_key") or ""),
                        "book_upstream_id": str(raw.get("book_upstream_id") or ""),
                    },
                }
            )
        relation_types = {
            "is_part_of": "IS_PART_OF",
            "appears_in": "APPEARS_IN",
            "is_a": "IS_A",
            "prerequisites_for": "PREREQUISITE_FOR",
            "relates_to": "RELATES_TO",
        }
        edges = []
        seen_edges = set()
        for raw in raw_edges:
            if not isinstance(raw, Mapping):
                raise SemanticaGraphIntegrityError("curriculum graph edge is invalid")
            package_key = str(raw.get("package_key") or "").strip()
            version_key = str(raw.get("version_key") or "").strip()
            relation = str(raw.get("relation_type") or "").strip()
            edge_type = relation_types.get(relation)
            source_id = _stable_id(
                "curriculum-base", package_key, version_key, raw.get("source_node_key")
            )
            target_id = _stable_id(
                "curriculum-base", package_key, version_key, raw.get("target_node_key")
            )
            if not edge_type or source_id not in known or target_id not in known:
                raise SemanticaGraphIntegrityError("curriculum graph edge scope is invalid")
            edge_id = _stable_id("curriculum-edge", version_key, relation, source_id, target_id)
            if edge_id in seen_edges:
                raise SemanticaGraphIntegrityError("curriculum graph edge is duplicated")
            seen_edges.add(edge_id)
            edges.append(
                {
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type,
                    "metadata": {
                        "scope_type": "curriculum",
                        "package_key": package_key,
                        "version_key": version_key,
                        "subject_key": str(raw.get("subject_key") or ""),
                    },
                }
            )
        expected_node_count = snapshot.get("node_count")
        expected_edge_count = snapshot.get("edge_count")
        if (
            not isinstance(expected_node_count, int)
            or not isinstance(expected_edge_count, int)
            or len(nodes) != expected_node_count
            or len(edges) != expected_edge_count
        ):
            raise SemanticaGraphIntegrityError("curriculum graph snapshot count mismatch")
        return nodes, edges

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
        curriculum_package_key = str(event.get("curriculum_package_key") or "").strip()
        curriculum_version_key = str(event.get("curriculum_version_key") or "").strip()
        if curriculum_package_key and curriculum_version_key:
            kp_node = _stable_id(
                "curriculum-knowledge-point",
                organization_id,
                subject_key,
                curriculum_package_key,
                curriculum_version_key,
                knowledge_point_key,
            )
        else:
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
                    "subject_key": subject_key,
                    "knowledge_point_key": knowledge_point_key,
                    "registry_version": int(event.get("registry_version") or 1),
                    "organization_id": organization_id,
                    "curriculum_package_key": curriculum_package_key,
                    "curriculum_version_key": curriculum_version_key,
                    "curriculum_source_revision": str(event.get("curriculum_source_revision") or ""),
                    "curriculum_content_hash": str(event.get("curriculum_content_hash") or ""),
                    "curriculum_node_content_hash": str(event.get("curriculum_node_content_hash") or ""),
                    "curriculum_node_id": int(event.get("curriculum_node_id") or 0),
                    "organization_knowledge_point_id": int(
                        event.get("organization_knowledge_point_id") or 0
                    ),
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

        if int(event.get("curriculum_node_id") or 0) and curriculum_package_key and curriculum_version_key:
            curriculum_base_node = _stable_id(
                "curriculum-base",
                curriculum_package_key,
                curriculum_version_key,
                knowledge_point_key,
            )
            edges.append(
                edge(kp_node, curriculum_base_node, "MAPS_TO_CURRICULUM", event_id)
            )

        curriculum_context = event.get("curriculum_context")
        if isinstance(curriculum_context, Mapping) and curriculum_package_key and curriculum_version_key:
            def curriculum_node(item: Mapping[str, object]) -> str:
                node_key = str(item.get("node_key") or "").strip()
                node_type = str(item.get("node_type") or "KnowledgePoint").strip()
                name = str(item.get("name") or item.get("canonical_name") or node_key)
                if not node_key:
                    raise SemanticaGraphIntegrityError("curriculum context node identity is missing")
                # The path includes the leaf knowledge point. It is already
                # represented by kp_node with frozen registry/source hashes;
                # appending a second node with the same ID would overwrite
                # those provenance properties during adapter deduplication.
                if node_key == knowledge_point_key:
                    return kp_node
                if node_type in {"Concept", "Skill", "KnowledgePoint"}:
                    node_id = _stable_id(
                        "curriculum-knowledge-point",
                        organization_id,
                        subject_key,
                        curriculum_package_key,
                        curriculum_version_key,
                        node_key,
                    )
                    properties = {
                        "organization_id": organization_id,
                        "subject_key": subject_key,
                        "knowledge_point_key": node_key,
                        "curriculum_package_key": curriculum_package_key,
                        "curriculum_version_key": curriculum_version_key,
                        "knowledge_point_kind": node_type,
                    }
                    graph_type = "KnowledgePoint"
                else:
                    node_id = _stable_id(
                        "curriculum-context",
                        organization_id,
                        student_id,
                        subject_key,
                        curriculum_version_key,
                        node_key,
                    )
                    properties = {
                        **scope,
                        "node_key": node_key,
                        "curriculum_package_key": curriculum_package_key,
                        "curriculum_version_key": curriculum_version_key,
                    }
                    graph_type = node_type
                nodes.append({"id": node_id, "type": graph_type, "content": name, "properties": properties})
                return node_id

            path = [item for item in curriculum_context.get("path") or [] if isinstance(item, Mapping)]
            path_ids = [curriculum_node(item) for item in path]
            for index in range(1, len(path_ids)):
                child_id = kp_node if index == len(path_ids) - 1 else path_ids[index]
                parent_id = path_ids[index - 1]
                relation = "APPEARS_IN" if index == len(path_ids) - 1 else "IS_PART_OF"
                edges.append(edge(child_id, parent_id, relation, event_id, index))
            for relation_key, edge_type, reverse in (
                ("prerequisites", "PREREQUISITE_FOR", False),
                ("follow_ups", "PREREQUISITE_FOR", True),
                ("related", "RELATES_TO", True),
            ):
                for index, item in enumerate(curriculum_context.get(relation_key) or []):
                    if not isinstance(item, Mapping):
                        continue
                    related_id = curriculum_node(item)
                    if relation_key == "prerequisites":
                        source_id, target_id = related_id, kp_node
                    else:
                        source_id, target_id = kp_node, related_id
                    edges.append(edge(source_id, target_id, edge_type, event_id, relation_key, index))

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
        deduplicated_nodes: dict[str, dict] = {}
        SemanticaGraphAdapter._upsert_nodes(deduplicated_nodes, nodes)
        return list(deduplicated_nodes.values()), edges

    def apply_event(
        self,
        event: Mapping[str, object],
        *,
        curriculum_snapshot: Optional[Mapping[str, object]] = None,
    ) -> dict:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            raise SemanticaGraphIntegrityError("trusted learning event identity is missing")
        desired_status = str(event.get("desired_status") or "")
        delete_event = desired_status == "deleted" or (
            desired_status == "superseded"
            and not str(event.get("superseded_by_event_id") or "").strip()
        )
        event_nodes, event_edges = ([], []) if delete_event else self._event_graph(event)
        curriculum_nodes, curriculum_edges = self._curriculum_graph(curriculum_snapshot)
        with self._exclusive_lock():
            existing = self._read_payload()
            edges_by_id = {
                str(edge["id"]): dict(edge)
                for edge in existing["edges"]
                if str((edge.get("metadata") or {}).get("event_id") or "")
                != event_id
            }
            edges_by_id.update({str(edge["id"]): edge for edge in curriculum_edges})
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
            self._upsert_nodes(nodes_by_id, curriculum_nodes)
            self._upsert_nodes(nodes_by_id, event_nodes)
            payload = self._canonicalize_with_semantica(nodes_by_id.values(), edges_by_id.values())
            self._atomic_write(payload)
        return {
            "event_id": event_id,
            "deleted": delete_event,
            "node_count": len(payload["nodes"]),
            "edge_count": len(payload["edges"]),
            "store_hash": hashlib.sha256(_canonical_json(payload).encode()).hexdigest(),
        }

    def rebuild(
        self,
        events: Iterable[Mapping[str, object]],
        *,
        curriculum_snapshot: Optional[Mapping[str, object]] = None,
    ) -> dict:
        nodes_by_id: dict[str, dict] = {}
        edges_by_id: dict[str, dict] = {}
        curriculum_nodes, curriculum_edges = self._curriculum_graph(curriculum_snapshot)
        self._upsert_nodes(nodes_by_id, curriculum_nodes)
        edges_by_id.update({str(edge["id"]): edge for edge in curriculum_edges})
        event_count = 0
        for event in events:
            event_nodes, event_edges = self._event_graph(event)
            self._upsert_nodes(nodes_by_id, event_nodes)
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

    def expected_store_hash(
        self,
        events: Iterable[Mapping[str, object]],
        *,
        curriculum_snapshot: Optional[Mapping[str, object]] = None,
    ) -> str:
        nodes_by_id: dict[str, dict] = {}
        edges_by_id: dict[str, dict] = {}
        curriculum_nodes, curriculum_edges = self._curriculum_graph(curriculum_snapshot)
        self._upsert_nodes(nodes_by_id, curriculum_nodes)
        edges_by_id.update({str(edge["id"]): edge for edge in curriculum_edges})
        for event in events:
            event_nodes, event_edges = self._event_graph(event)
            self._upsert_nodes(nodes_by_id, event_nodes)
            edges_by_id.update({str(edge["id"]): edge for edge in event_edges})
        payload = self._canonicalize_with_semantica(nodes_by_id.values(), edges_by_id.values())
        return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()

    def store_hash(self) -> str:
        payload = self._read_payload()
        self._trusted_learning_event_ids_from_payload(payload)
        return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()

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
            metadata = dict(edge.get("metadata") or {})
            if str(metadata.get("scope_type") or "") == "curriculum":
                continue
            if _scope(metadata) != expected:
                continue
            source_id = str(edge.get("source") or "")
            target_id = str(edge.get("target") or "")
            endpoints = [nodes_by_id.get(source_id), nodes_by_id.get(target_id)]
            if any(node is None for node in endpoints):
                raise SemanticaGraphScopeError("Semantica scoped edge endpoint is missing")
            for node in endpoints:
                properties = dict(node.get("properties") or node.get("metadata") or {})
                if str(properties.get("scope_type") or "") == "curriculum":
                    if str(properties.get("subject_key") or "") != expected[2]:
                        raise SemanticaGraphScopeError(
                            "Semantica curriculum node subject scope mismatch"
                        )
                    continue
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

    def readiness(self) -> dict:
        if not self.store_path.is_file():
            return {"healthy": False, "error": "store_missing"}
        try:
            store_size = self.store_path.stat().st_size
            with self.store_path.open("rb") as handle:
                prefix = handle.read(64).lstrip()
        except OSError:
            return {"healthy": False, "error": "store_unreadable"}
        if store_size <= 0 or not prefix.startswith(b"{"):
            return {"healthy": False, "error": "store_unreadable"}
        try:
            installed = self._installed_version()
        except SemanticaGraphUnavailableError:
            return {"healthy": False, "error": "semantica_unavailable"}
        return {
            "healthy": True,
            "semantica_version": installed,
            "store_size": store_size,
        }

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
        curriculum_node_count = sum(
            1
            for node in payload["nodes"]
            if str(
                (node.get("properties") or node.get("metadata") or {}).get("scope_type")
                or ""
            )
            == "curriculum"
        )
        curriculum_edge_count = sum(
            1
            for edge in payload["edges"]
            if str((edge.get("metadata") or {}).get("scope_type") or "")
            == "curriculum"
        )
        return {
            "healthy": True,
            "semantica_version": SEMANTICA_REQUIRED_VERSION,
            "node_count": len(payload["nodes"]),
            "edge_count": len(payload["edges"]),
            "event_count": len(event_ids),
            "curriculum_node_count": curriculum_node_count,
            "curriculum_edge_count": curriculum_edge_count,
        }
