from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional


CURRICULUM_SCHEMA_VERSION = "xingrun.curriculum-registry.v1"
CURRICULUM_IMPORTER_VERSION = "xingrun.k12-kgraph-importer.v1"
CURRICULUM_PACKAGE_KEY = "pep.math.k12-kgraph"
CURRICULUM_VERSION_KEY = "pep.math.k12-kgraph.d8522c2b336e"
CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION = "class_curriculum_assignment.v2"
SOURCE_GITHUB_URL = "https://github.com/haolpku/K12-KGraph"
SOURCE_GITHUB_COMMIT = "8716b6a80850790f509c01286f43e5bfe6858f49"
SOURCE_DATASET_URL = "https://huggingface.co/datasets/lhpku20010120/K12-KGraph"
SOURCE_DATASET_REVISION = "d8522c2b336ee435aa51daa39ca0dd736f56fa53"
SOURCE_FILE_PATH = "K12-KGraph/subject_specific_KG/math.json"
SOURCE_SHA256 = "00ed25179bb4ad096c53b3965fe84a32afa708850de85db5ea4c9e0bacec8f14"
SOURCE_DATA_LICENSE = "CC BY-NC-SA 4.0"
SOURCE_CODE_LICENSE = "MIT"

EXPECTED_SOURCE_NODE_COUNTS = {
    "Book": 23,
    "Chapter": 150,
    "Section": 166,
    "Concept": 1470,
    "Skill": 428,
    "Exercise": 474,
}
EXPECTED_SOURCE_EDGE_COUNTS = {
    "appears_in": 2621,
    "is_a": 287,
    "prerequisites_for": 853,
    "relates_to": 405,
    "is_part_of": 316,
    "tests_concept": 406,
    "tests_skill": 229,
    "leads_to": 156,
}
EXPECTED_IMPORT_NODE_COUNTS = {
    "Book": 23,
    "Chapter": 150,
    "Section": 166,
    "Concept": 1470,
    "Skill": 428,
}
EXPECTED_IMPORT_EDGE_COUNTS = {
    "appears_in": 2146,
    "is_a": 287,
    "prerequisites_for": 853,
    "relates_to": 405,
    "is_part_of": 316,
}
ALLOWED_NODE_TYPES = frozenset(EXPECTED_IMPORT_NODE_COUNTS)
KNOWLEDGE_POINT_TYPES = frozenset({"Concept", "Skill"})
ALLOWED_EDGE_TYPES = frozenset(EXPECTED_IMPORT_EDGE_COUNTS)
VERSION_STATUSES = frozenset({"draft", "reviewed", "active", "deprecated"})
LEGACY_KNOWLEDGE_POINT_TARGETS = {
    "math.quadratic_function_graph": "math_9a_rjb_cpt17",
    "math.derivative_basics": "math_xzxbx2_rjb_cpt33",
}

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_BUNDLE_PATH = BASE_DIR / "data" / "curriculum" / "pep_math_k12_kgraph_d8522c2b.json"
DEFAULT_RECEIPT_PATH = BASE_DIR / "data" / "curriculum" / "pep_math_k12_kgraph_d8522c2b.receipt.json"

_BOOK_PREFIX_RE = re.compile(r"^(math_(?:[1-9][ab]|bx[12]|xzxbx[123])_rjb)(?:_|$)")


class CurriculumValidationError(ValueError):
    pass


class CurriculumConflictError(ValueError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: object) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()


def _begin_immediate_if_needed(conn: sqlite3.Connection) -> None:
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")


def _normalized_positive_ids(values: Iterable[object], *, label: str) -> list[int]:
    normalized = set()
    try:
        items = list(values)
    except TypeError as exc:
        raise CurriculumValidationError(f"{label} must be a list of integers") from exc
    for value in items:
        if isinstance(value, bool):
            raise CurriculumValidationError(f"{label} must contain only positive integers")
        try:
            normalized_value = int(value)
        except (TypeError, ValueError) as exc:
            raise CurriculumValidationError(
                f"{label} must contain only positive integers"
            ) from exc
        if normalized_value <= 0 or str(value).strip() != str(normalized_value):
            raise CurriculumValidationError(f"{label} must contain only positive integers")
        normalized.add(normalized_value)
    return sorted(normalized)


def normalize_alias(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.split()).casefold()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _book_upstream_id(upstream_id: object) -> str:
    match = _BOOK_PREFIX_RE.match(str(upstream_id or ""))
    if not match:
        raise CurriculumValidationError(f"unsupported math node id: {upstream_id}")
    return match.group(1)


def _book_scope(book: Mapping[str, object]) -> tuple[str, str, str]:
    upstream_id = str(book.get("id") or "")
    name = str(book.get("name") or "")
    if re.fullmatch(r"math_[1-6][ab]_rjb", upstream_id):
        stage = "primary"
    elif re.fullmatch(r"math_[7-9][ab]_rjb", upstream_id):
        stage = "junior"
    elif re.fullmatch(r"math_(?:bx[12]|xzxbx[123])_rjb", upstream_id):
        stage = "senior"
    else:
        raise CurriculumValidationError(f"unsupported book id: {upstream_id}")
    grade_match = re.search(r"([一二三四五六七八九])年级", name)
    grade = f"grade_{'一二三四五六七八九'.index(grade_match.group(1)) + 1}" if grade_match else "senior"
    semester = "first" if name.endswith("上册") else "second" if name.endswith("下册") else "required"
    if name.startswith("选择性必修"):
        semester = "selective_required"
    return stage, grade, semester


def ensure_curriculum_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS curriculum_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_key TEXT NOT NULL UNIQUE,
            curriculum_name TEXT NOT NULL,
            subject_key TEXT NOT NULL,
            publisher_name TEXT NOT NULL,
            edition_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            data_license TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            CHECK(package_key<>''), CHECK(subject_key<>'')
        );

        CREATE TABLE IF NOT EXISTS curriculum_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER NOT NULL REFERENCES curriculum_packages(id) ON DELETE CASCADE,
            version_key TEXT NOT NULL UNIQUE,
            registry_version INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            source_dataset_url TEXT NOT NULL,
            source_dataset_revision TEXT NOT NULL,
            source_file_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            source_github_url TEXT NOT NULL,
            source_github_commit TEXT NOT NULL,
            data_license TEXT NOT NULL,
            code_license TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            source_counts_json TEXT NOT NULL,
            import_counts_json TEXT NOT NULL,
            importer_version TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            imported_by_user_id INTEGER,
            reviewed_at TEXT,
            reviewed_by_user_id INTEGER,
            activated_at TEXT,
            activated_by_user_id INTEGER,
            deprecated_at TEXT,
            deprecated_by_user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(package_id, registry_version),
            CHECK(status IN ('draft','reviewed','active','deprecated')),
            CHECK(registry_version >= 1),
            CHECK(length(source_sha256)=64), CHECK(length(content_hash)=64)
        );

        CREATE TABLE IF NOT EXISTS curriculum_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL REFERENCES curriculum_versions(id) ON DELETE CASCADE,
            node_key TEXT NOT NULL,
            upstream_id TEXT NOT NULL,
            node_type TEXT NOT NULL,
            knowledge_point_kind TEXT,
            subject_key TEXT NOT NULL,
            book_upstream_id TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            aliases_json TEXT NOT NULL DEFAULT '[]',
            description TEXT NOT NULL DEFAULT '',
            importance TEXT NOT NULL DEFAULT '',
            source_locator TEXT NOT NULL DEFAULT '',
            stage_key TEXT NOT NULL,
            grade_key TEXT NOT NULL,
            semester_key TEXT NOT NULL,
            source_properties_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(version_id, node_key),
            UNIQUE(version_id, upstream_id),
            CHECK(node_type IN ('Book','Chapter','Section','Concept','Skill')),
            CHECK(subject_key<>''), CHECK(book_upstream_id<>''), CHECK(canonical_name<>'')
        );

        CREATE TABLE IF NOT EXISTS curriculum_node_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL REFERENCES curriculum_versions(id) ON DELETE CASCADE,
            node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
            subject_key TEXT NOT NULL,
            book_upstream_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'upstream',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(version_id, node_id, normalized_alias),
            CHECK(alias<>''), CHECK(normalized_alias<>'')
        );

        CREATE TABLE IF NOT EXISTS curriculum_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL REFERENCES curriculum_versions(id) ON DELETE CASCADE,
            source_node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
            target_node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
            relation_type TEXT NOT NULL,
            source_properties_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(version_id, source_node_id, target_node_id, relation_type),
            CHECK(relation_type IN ('is_part_of','appears_in','is_a','prerequisites_for','relates_to')),
            CHECK(source_node_id<>target_node_id)
        );

        CREATE TABLE IF NOT EXISTS curriculum_book_nodes (
            version_id INTEGER NOT NULL REFERENCES curriculum_versions(id) ON DELETE CASCADE,
            book_node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
            node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
            membership_type TEXT NOT NULL,
            PRIMARY KEY (version_id, book_node_id, node_id),
            CHECK(membership_type IN ('structural','appears_in'))
        );

        CREATE TABLE IF NOT EXISTS curriculum_class_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            version_id INTEGER NOT NULL REFERENCES curriculum_versions(id),
            book_node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id),
            status TEXT NOT NULL DEFAULT 'active',
            assigned_by_user_id INTEGER REFERENCES users(id),
            assigned_at TEXT NOT NULL,
            ended_at TEXT,
            note TEXT NOT NULL DEFAULT '',
            request_id TEXT NOT NULL DEFAULT '',
            payload_hash TEXT NOT NULL DEFAULT '',
            expected_previous_assignment_id INTEGER,
            CHECK(status IN ('active','superseded','removed'))
        );

        CREATE TABLE IF NOT EXISTS curriculum_assignment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            request_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            assignment_id INTEGER REFERENCES curriculum_class_assignments(id) ON DELETE SET NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(organization_id, request_id),
            CHECK(request_id<>''), CHECK(length(payload_hash)=64)
        );

        CREATE TABLE IF NOT EXISTS curriculum_organization_knowledge_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            version_id INTEGER NOT NULL REFERENCES curriculum_versions(id),
            book_node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id),
            subject_key TEXT NOT NULL,
            knowledge_point_key TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'proposed',
            proposed_by_user_id INTEGER REFERENCES users(id),
            reviewed_by_user_id INTEGER REFERENCES users(id),
            proposed_at TEXT NOT NULL,
            reviewed_at TEXT,
            UNIQUE(organization_id, knowledge_point_key),
            CHECK(status IN ('proposed','reviewed','active','rejected','deprecated'))
        );

        CREATE TABLE IF NOT EXISTS curriculum_organization_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            version_id INTEGER NOT NULL REFERENCES curriculum_versions(id),
            book_node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id),
            subject_key TEXT NOT NULL,
            curriculum_node_id INTEGER REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
            organization_knowledge_point_id INTEGER REFERENCES curriculum_organization_knowledge_points(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_by_user_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            UNIQUE(organization_id, version_id, book_node_id, normalized_alias),
            CHECK(status IN ('active','deprecated')),
            CHECK((curriculum_node_id IS NULL)<>(organization_knowledge_point_id IS NULL))
        );

        CREATE TABLE IF NOT EXISTS curriculum_mapping_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            candidate_id TEXT NOT NULL,
            request_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL,
            target_knowledge_point_key TEXT,
            proposed_name TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            actor_user_id INTEGER NOT NULL REFERENCES users(id),
            reviewed_by_user_id INTEGER REFERENCES users(id),
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            UNIQUE(organization_id, request_id),
            CHECK(action_type IN ('map','add_alias','propose_new','reject','approve_proposal','reject_proposal')),
            CHECK(status IN ('applied','pending_review','approved','rejected','failed'))
        );

        CREATE TABLE IF NOT EXISTS curriculum_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER,
            package_id INTEGER REFERENCES curriculum_packages(id) ON DELETE SET NULL,
            version_id INTEGER REFERENCES curriculum_versions(id) ON DELETE SET NULL,
            class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_key TEXT NOT NULL,
            before_json TEXT NOT NULL DEFAULT '{}',
            after_json TEXT NOT NULL DEFAULT '{}',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            CHECK(action<>''), CHECK(target_type<>''), CHECK(target_key<>'')
        );

        CREATE TABLE IF NOT EXISTS curriculum_legacy_knowledge_point_map (
            legacy_knowledge_point_key TEXT NOT NULL,
            version_id INTEGER NOT NULL REFERENCES curriculum_versions(id) ON DELETE CASCADE,
            curriculum_node_id INTEGER NOT NULL REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
            mapping_note TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(legacy_knowledge_point_key, version_id)
        );

        CREATE INDEX IF NOT EXISTS idx_curriculum_nodes_catalog
        ON curriculum_nodes(version_id, node_type, stage_key, grade_key, book_upstream_id, canonical_name);
        CREATE INDEX IF NOT EXISTS idx_curriculum_alias_lookup
        ON curriculum_node_aliases(version_id, subject_key, book_upstream_id, normalized_alias);
        CREATE INDEX IF NOT EXISTS idx_curriculum_edge_source
        ON curriculum_edges(version_id, source_node_id, relation_type);
        CREATE INDEX IF NOT EXISTS idx_curriculum_edge_target
        ON curriculum_edges(version_id, target_node_id, relation_type);
        CREATE INDEX IF NOT EXISTS idx_curriculum_book_nodes_lookup
        ON curriculum_book_nodes(version_id, book_node_id, node_id, membership_type);
        CREATE INDEX IF NOT EXISTS idx_curriculum_mapping_candidate
        ON curriculum_mapping_actions(organization_id, candidate_id, created_at);

        CREATE TRIGGER IF NOT EXISTS curriculum_nodes_immutable_update
        BEFORE UPDATE ON curriculum_nodes
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum nodes are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_nodes_immutable_insert
        BEFORE INSERT ON curriculum_nodes
        WHEN (SELECT status FROM curriculum_versions WHERE id=NEW.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum nodes are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_nodes_immutable_delete
        BEFORE DELETE ON curriculum_nodes
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum nodes are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_aliases_immutable_update
        BEFORE UPDATE ON curriculum_node_aliases
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum aliases are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_aliases_immutable_insert
        BEFORE INSERT ON curriculum_node_aliases
        WHEN (SELECT status FROM curriculum_versions WHERE id=NEW.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum aliases are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_aliases_immutable_delete
        BEFORE DELETE ON curriculum_node_aliases
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum aliases are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_edges_immutable_update
        BEFORE UPDATE ON curriculum_edges
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum edges are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_edges_immutable_insert
        BEFORE INSERT ON curriculum_edges
        WHEN (SELECT status FROM curriculum_versions WHERE id=NEW.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum edges are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_edges_immutable_delete
        BEFORE DELETE ON curriculum_edges
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum edges are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_book_nodes_immutable_update
        BEFORE UPDATE ON curriculum_book_nodes
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum membership is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_book_nodes_immutable_insert
        BEFORE INSERT ON curriculum_book_nodes
        WHEN (SELECT status FROM curriculum_versions WHERE id=NEW.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum membership is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_book_nodes_immutable_delete
        BEFORE DELETE ON curriculum_book_nodes
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum membership is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_legacy_map_immutable_update
        BEFORE UPDATE ON curriculum_legacy_knowledge_point_map
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum legacy mapping is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_legacy_map_immutable_insert
        BEFORE INSERT ON curriculum_legacy_knowledge_point_map
        WHEN (SELECT status FROM curriculum_versions WHERE id=NEW.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum legacy mapping is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_legacy_map_immutable_delete
        BEFORE DELETE ON curriculum_legacy_knowledge_point_map
        WHEN (SELECT status FROM curriculum_versions WHERE id=OLD.version_id) IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum legacy mapping is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_version_source_immutable
        BEFORE UPDATE OF package_id, version_key, registry_version,
            source_dataset_url, source_dataset_revision, source_file_path,
            source_sha256, source_github_url, source_github_commit, data_license,
            code_license, content_hash, source_counts_json, import_counts_json,
            importer_version, imported_at, imported_by_user_id
        ON curriculum_versions
        WHEN OLD.status IN ('reviewed','active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum provenance is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_version_no_return_to_draft
        BEFORE UPDATE OF status ON curriculum_versions
        WHEN OLD.status IN ('reviewed','active','deprecated') AND NEW.status='draft'
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum cannot return to draft'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_package_immutable_update
        BEFORE UPDATE ON curriculum_packages
        WHEN EXISTS (
            SELECT 1 FROM curriculum_versions version
            WHERE version.package_id=OLD.id
              AND version.status IN ('reviewed','active','deprecated')
        )
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum package is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_package_immutable_delete
        BEFORE DELETE ON curriculum_packages
        WHEN EXISTS (
            SELECT 1 FROM curriculum_versions version
            WHERE version.package_id=OLD.id
              AND version.status IN ('reviewed','active','deprecated')
        )
        BEGIN SELECT RAISE(ABORT, 'reviewed curriculum package is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS curriculum_org_kp_active_identity_immutable
        BEFORE UPDATE OF organization_id, version_id, book_node_id, subject_key,
            knowledge_point_key, canonical_name, description
        ON curriculum_organization_knowledge_points
        WHEN OLD.status IN ('active','deprecated')
        BEGIN SELECT RAISE(ABORT, 'active organization knowledge point is immutable'); END;
        """
    )
    _ensure_column(conn, "curriculum_class_assignments", "request_id", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "curriculum_class_assignments", "payload_hash", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "curriculum_class_assignments", "expected_previous_assignment_id", "INTEGER")
    _ensure_column(conn, "curriculum_class_assignments", "is_primary", "INTEGER NOT NULL DEFAULT 0")
    conn.execute("DROP INDEX IF EXISTS idx_curriculum_class_assignment_active")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_curriculum_class_assignment_active_book
        ON curriculum_class_assignments(class_id, version_id, book_node_id)
        WHERE status='active'
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_curriculum_class_assignment_request
        ON curriculum_class_assignments(organization_id, request_id) WHERE request_id<>''
        """
    )


def _edge_targets(edge: Mapping[str, object]) -> list[str]:
    if str(edge.get("target") or ""):
        return [str(edge["target"])]
    targets = edge.get("target_name_to_ids")
    if not isinstance(targets, list):
        return []
    return [str(item.get("target") or "") for item in targets if isinstance(item, Mapping) and item.get("target")]


def build_bundle_from_upstream(raw_bytes: bytes) -> dict:
    if hashlib.sha256(raw_bytes).hexdigest() != SOURCE_SHA256:
        raise CurriculumValidationError("pinned upstream SHA-256 mismatch")
    try:
        source = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurriculumValidationError("upstream math.json is invalid JSON") from exc
    if not isinstance(source, Mapping) or set(source) != {"nodes", "edges"}:
        raise CurriculumValidationError("upstream root structure mismatch")
    nodes = source.get("nodes")
    edges = source.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise CurriculumValidationError("upstream nodes or edges are invalid")
    node_counts = Counter(str(item.get("label") or "") for item in nodes if isinstance(item, Mapping))
    edge_counts = Counter(str(item.get("type") or "") for item in edges if isinstance(item, Mapping))
    if dict(node_counts) != EXPECTED_SOURCE_NODE_COUNTS or dict(edge_counts) != EXPECTED_SOURCE_EDGE_COUNTS:
        raise CurriculumValidationError("pinned upstream parsed counts mismatch")
    filtered_nodes = [dict(item) for item in nodes if isinstance(item, Mapping) and item.get("label") in ALLOWED_NODE_TYPES]
    included_ids = {str(item.get("id") or "") for item in filtered_nodes}
    filtered_edges = []
    for edge in edges:
        if not isinstance(edge, Mapping) or str(edge.get("type") or "") not in ALLOWED_EDGE_TYPES:
            continue
        source_id = str(edge.get("source") or "")
        if source_id not in included_ids:
            continue
        for target_id in _edge_targets(edge):
            if target_id not in included_ids:
                continue
            filtered_edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "type": str(edge["type"]),
                    "properties": dict(edge.get("properties") or {}),
                }
            )
    bundle = {
        "schema_version": CURRICULUM_SCHEMA_VERSION,
        "package_key": CURRICULUM_PACKAGE_KEY,
        "version_key": CURRICULUM_VERSION_KEY,
        "source": {
            "github_url": SOURCE_GITHUB_URL,
            "github_commit": SOURCE_GITHUB_COMMIT,
            "dataset_url": SOURCE_DATASET_URL,
            "dataset_revision": SOURCE_DATASET_REVISION,
            "file_path": SOURCE_FILE_PATH,
            "sha256": SOURCE_SHA256,
            "data_license": SOURCE_DATA_LICENSE,
            "code_license": SOURCE_CODE_LICENSE,
        },
        "source_counts": {"nodes": EXPECTED_SOURCE_NODE_COUNTS, "edges": EXPECTED_SOURCE_EDGE_COUNTS},
        "import_counts": {"nodes": EXPECTED_IMPORT_NODE_COUNTS, "edges": EXPECTED_IMPORT_EDGE_COUNTS},
        "nodes": sorted(filtered_nodes, key=lambda item: str(item.get("id") or "")),
        "edges": sorted(filtered_edges, key=lambda item: (item["type"], item["source"], item["target"])),
    }
    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle: Mapping[str, object]) -> dict:
    if str(bundle.get("schema_version") or "") != CURRICULUM_SCHEMA_VERSION:
        raise CurriculumValidationError("curriculum bundle schema mismatch")
    if str(bundle.get("package_key") or "") != CURRICULUM_PACKAGE_KEY:
        raise CurriculumValidationError("curriculum package key mismatch")
    if str(bundle.get("version_key") or "") != CURRICULUM_VERSION_KEY:
        raise CurriculumValidationError("curriculum version key mismatch")
    source = bundle.get("source")
    expected_source = {
        "github_url": SOURCE_GITHUB_URL,
        "github_commit": SOURCE_GITHUB_COMMIT,
        "dataset_url": SOURCE_DATASET_URL,
        "dataset_revision": SOURCE_DATASET_REVISION,
        "file_path": SOURCE_FILE_PATH,
        "sha256": SOURCE_SHA256,
        "data_license": SOURCE_DATA_LICENSE,
        "code_license": SOURCE_CODE_LICENSE,
    }
    if not isinstance(source, Mapping) or dict(source) != expected_source:
        raise CurriculumValidationError("curriculum source receipt mismatch")
    if bundle.get("source_counts") != {"nodes": EXPECTED_SOURCE_NODE_COUNTS, "edges": EXPECTED_SOURCE_EDGE_COUNTS}:
        raise CurriculumValidationError("curriculum source counts receipt mismatch")
    if bundle.get("import_counts") != {"nodes": EXPECTED_IMPORT_NODE_COUNTS, "edges": EXPECTED_IMPORT_EDGE_COUNTS}:
        raise CurriculumValidationError("curriculum import counts receipt mismatch")
    nodes = bundle.get("nodes")
    edges = bundle.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise CurriculumValidationError("curriculum bundle payload is invalid")
    node_counts = Counter()
    nodes_by_id = {}
    books = {}
    for raw in nodes:
        if not isinstance(raw, Mapping):
            raise CurriculumValidationError("curriculum node is invalid")
        upstream_id = str(raw.get("id") or "")
        node_type = str(raw.get("label") or "")
        name = str(raw.get("name") or "").strip()
        if node_type not in ALLOWED_NODE_TYPES or node_type == "Exercise":
            raise CurriculumValidationError("forbidden curriculum node type")
        if not upstream_id or not name or upstream_id in nodes_by_id:
            raise CurriculumValidationError("curriculum node identity is invalid")
        _book_upstream_id(upstream_id)
        nodes_by_id[upstream_id] = raw
        node_counts[node_type] += 1
        if node_type == "Book":
            books[upstream_id] = raw
    if dict(node_counts) != EXPECTED_IMPORT_NODE_COUNTS or len(nodes_by_id) != 2237 or len(books) != 23:
        raise CurriculumValidationError("curriculum imported node counts mismatch")
    edge_counts = Counter()
    seen_edges = set()
    prereq_adj: dict[str, list[str]] = defaultdict(list)
    prereq_indegree: Counter[str] = Counter()
    prereq_nodes = set()
    for raw in edges:
        if not isinstance(raw, Mapping) or set(raw) != {"source", "target", "type", "properties"}:
            raise CurriculumValidationError("curriculum edge contract mismatch")
        source_id = str(raw.get("source") or "")
        target_id = str(raw.get("target") or "")
        edge_type = str(raw.get("type") or "")
        identity = (source_id, target_id, edge_type)
        if edge_type not in ALLOWED_EDGE_TYPES or source_id not in nodes_by_id or target_id not in nodes_by_id:
            raise CurriculumValidationError("curriculum edge scope mismatch")
        if source_id == target_id or identity in seen_edges:
            raise CurriculumValidationError("duplicate or self-referencing curriculum edge")
        seen_edges.add(identity)
        edge_counts[edge_type] += 1
        if edge_type == "prerequisites_for":
            prereq_adj[source_id].append(target_id)
            prereq_indegree[target_id] += 1
            prereq_nodes.update((source_id, target_id))
    if dict(edge_counts) != EXPECTED_IMPORT_EDGE_COUNTS or len(seen_edges) != 4007:
        raise CurriculumValidationError("curriculum imported edge counts mismatch")
    queue = deque(sorted(node for node in prereq_nodes if prereq_indegree[node] == 0))
    visited = 0
    while queue:
        source_id = queue.popleft()
        visited += 1
        for target_id in prereq_adj[source_id]:
            prereq_indegree[target_id] -= 1
            if prereq_indegree[target_id] == 0:
                queue.append(target_id)
    if visited != len(prereq_nodes):
        raise CurriculumValidationError("prerequisite cycle detected")
    content = {"nodes": nodes, "edges": edges}
    return {
        "node_counts": dict(node_counts),
        "edge_counts": dict(edge_counts),
        "node_total": len(nodes_by_id),
        "edge_total": len(seen_edges),
        "knowledge_point_total": node_counts["Concept"] + node_counts["Skill"],
        "content_hash": content_hash(content),
    }


def load_bundle(path: Path | str = DEFAULT_BUNDLE_PATH, receipt_path: Path | str = DEFAULT_RECEIPT_PATH) -> dict:
    bundle_path = Path(path)
    receipt_file = Path(receipt_path)
    raw = bundle_path.read_bytes()
    try:
        bundle = json.loads(raw)
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        raise CurriculumValidationError("curriculum bundle or receipt cannot be read") from exc
    bundle_sha256 = hashlib.sha256(raw).hexdigest()
    if not isinstance(receipt, Mapping) or str(receipt.get("bundle_sha256") or "") != bundle_sha256:
        raise CurriculumValidationError("curriculum bundle SHA-256 mismatch")
    stats = validate_bundle(bundle)
    if str(receipt.get("content_hash") or "") != stats["content_hash"]:
        raise CurriculumValidationError("curriculum bundle content hash mismatch")
    if str(receipt.get("source_sha256") or "") != SOURCE_SHA256:
        raise CurriculumValidationError("curriculum source receipt SHA-256 mismatch")
    expected_receipt = {
        "schema_version": "xingrun.curriculum-source-receipt.v1",
        "bundle_path": bundle_path.name,
        "source_dataset_url": SOURCE_DATASET_URL,
        "source_dataset_revision": SOURCE_DATASET_REVISION,
        "source_file_path": SOURCE_FILE_PATH,
        "source_github_url": SOURCE_GITHUB_URL,
        "source_github_commit": SOURCE_GITHUB_COMMIT,
        "data_license": SOURCE_DATA_LICENSE,
        "code_license": SOURCE_CODE_LICENSE,
        "source_counts": {
            "nodes": EXPECTED_SOURCE_NODE_COUNTS,
            "edges": EXPECTED_SOURCE_EDGE_COUNTS,
        },
        "import_counts": {
            "nodes": EXPECTED_IMPORT_NODE_COUNTS,
            "edges": EXPECTED_IMPORT_EDGE_COUNTS,
        },
        "importer_version": CURRICULUM_IMPORTER_VERSION,
        "contains_exercises": False,
    }
    if any(receipt.get(key) != value for key, value in expected_receipt.items()):
        raise CurriculumValidationError("curriculum source receipt provenance mismatch")
    return dict(bundle)


def _audit(
    conn: sqlite3.Connection,
    *,
    action: str,
    target_type: str,
    target_key: str,
    actor_user_id: Optional[int],
    organization_id: Optional[int] = None,
    package_id: Optional[int] = None,
    version_id: Optional[int] = None,
    class_id: Optional[int] = None,
    before: object = None,
    after: object = None,
    note: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO curriculum_audit_events (
            organization_id, package_id, version_id, class_id, actor_user_id,
            action, target_type, target_key, before_json, after_json, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id,
            package_id,
            version_id,
            class_id,
            actor_user_id,
            action,
            target_type,
            target_key,
            canonical_json(before or {}),
            canonical_json(after or {}),
            str(note or ""),
            _utc_now(),
        ),
    )


def _materialize_book_membership(conn: sqlite3.Connection, version_id: int) -> None:
    """Freeze graph-derived book membership for deterministic scoped lookup."""
    conn.execute("DELETE FROM curriculum_book_nodes WHERE version_id=?", (int(version_id),))
    books = conn.execute(
        "SELECT id FROM curriculum_nodes WHERE version_id=? AND node_type='Book' ORDER BY upstream_id",
        (int(version_id),),
    ).fetchall()
    for book in books:
        book_id = int(book["id"])
        conn.execute(
            """
            WITH RECURSIVE structural(node_id) AS (
                SELECT ?
                UNION
                SELECT edge.source_node_id
                FROM curriculum_edges edge
                JOIN structural parent ON parent.node_id=edge.target_node_id
                JOIN curriculum_nodes child ON child.id=edge.source_node_id
                WHERE edge.version_id=? AND edge.relation_type='is_part_of'
                  AND child.node_type IN ('Chapter','Section')
            )
            INSERT INTO curriculum_book_nodes (
                version_id, book_node_id, node_id, membership_type
            )
            SELECT ?, ?, node_id, 'structural' FROM structural
            """,
            (book_id, int(version_id), int(version_id), book_id),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO curriculum_book_nodes (
                version_id, book_node_id, node_id, membership_type
            )
            SELECT ?, ?, edge.source_node_id, 'appears_in'
            FROM curriculum_edges edge
            JOIN curriculum_book_nodes target_membership
              ON target_membership.version_id=edge.version_id
             AND target_membership.book_node_id=?
             AND target_membership.node_id=edge.target_node_id
             AND target_membership.membership_type='structural'
            JOIN curriculum_nodes source ON source.id=edge.source_node_id
            WHERE edge.version_id=? AND edge.relation_type='appears_in'
              AND source.node_type IN ('Concept','Skill')
            """,
            (int(version_id), book_id, book_id, int(version_id)),
        )


def import_curriculum_bundle(
    conn: sqlite3.Connection,
    bundle: Mapping[str, object],
    *,
    actor_user_id: Optional[int],
    fail_after_nodes: Optional[int] = None,
) -> dict:
    ensure_curriculum_schema(conn)
    stats = validate_bundle(bundle)
    existing = conn.execute(
        "SELECT * FROM curriculum_versions WHERE version_key=?",
        (CURRICULUM_VERSION_KEY,),
    ).fetchone()
    if existing:
        if str(existing["content_hash"]) != stats["content_hash"]:
            raise CurriculumConflictError("installed curriculum version content differs")
        verify_installed_curriculum(conn, int(existing["id"]))
        return {"changed": False, "version": dict(existing), **stats}
    savepoint = "curriculum_import_v1"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        conn.execute(
            """
            INSERT INTO curriculum_packages (
                package_key, curriculum_name, subject_key, publisher_name,
                edition_name, source_url, data_license
            ) VALUES (?, ?, 'math', ?, ?, ?, ?)
            ON CONFLICT(package_key) DO NOTHING
            """,
            (
                CURRICULUM_PACKAGE_KEY,
                "人教版数学课程知识图谱",
                "人民教育出版社",
                "人教版; 高中为 A 版; 出版年份未指定",
                SOURCE_DATASET_URL,
                SOURCE_DATA_LICENSE,
            ),
        )
        package = conn.execute(
            "SELECT * FROM curriculum_packages WHERE package_key=?",
            (CURRICULUM_PACKAGE_KEY,),
        ).fetchone()
        imported_at = _utc_now()
        cursor = conn.execute(
            """
            INSERT INTO curriculum_versions (
                package_id, version_key, registry_version, status,
                source_dataset_url, source_dataset_revision, source_file_path,
                source_sha256, source_github_url, source_github_commit,
                data_license, code_license, content_hash, source_counts_json,
                import_counts_json, importer_version, imported_at, imported_by_user_id
            ) VALUES (?, ?, 1, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(package["id"]),
                CURRICULUM_VERSION_KEY,
                SOURCE_DATASET_URL,
                SOURCE_DATASET_REVISION,
                SOURCE_FILE_PATH,
                SOURCE_SHA256,
                SOURCE_GITHUB_URL,
                SOURCE_GITHUB_COMMIT,
                SOURCE_DATA_LICENSE,
                SOURCE_CODE_LICENSE,
                stats["content_hash"],
                canonical_json(bundle["source_counts"]),
                canonical_json(bundle["import_counts"]),
                CURRICULUM_IMPORTER_VERSION,
                imported_at,
                actor_user_id,
            ),
        )
        version_id = int(cursor.lastrowid)
        books = {str(node["id"]): node for node in bundle["nodes"] if node["label"] == "Book"}
        node_id_by_upstream = {}
        for index, node in enumerate(bundle["nodes"], start=1):
            upstream_id = str(node["id"])
            book_upstream_id = _book_upstream_id(upstream_id)
            book = books[book_upstream_id]
            stage_key, grade_key, semester_key = _book_scope(book)
            properties = dict(node.get("properties") or {})
            node_type = str(node["label"])
            aliases = properties.get("aliases") if isinstance(properties.get("aliases"), list) else []
            aliases = [str(alias).strip() for alias in aliases if str(alias).strip()]
            description = str(properties.get("definition") or properties.get("description") or "").strip()
            source_locator = str(properties.get("pages") or "").strip()
            node_key = f"k12kg.{upstream_id}"
            inserted = conn.execute(
                """
                INSERT INTO curriculum_nodes (
                    version_id, node_key, upstream_id, node_type, knowledge_point_kind,
                    subject_key, book_upstream_id, canonical_name, aliases_json,
                    description, importance, source_locator, stage_key, grade_key,
                    semester_key, source_properties_json
                ) VALUES (?, ?, ?, ?, ?, 'math', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    node_key,
                    upstream_id,
                    node_type,
                    node_type if node_type in KNOWLEDGE_POINT_TYPES else None,
                    book_upstream_id,
                    str(node["name"]).strip(),
                    canonical_json(aliases),
                    description,
                    str(properties.get("importance") or "").strip(),
                    source_locator,
                    stage_key,
                    grade_key,
                    semester_key,
                    canonical_json(properties),
                ),
            )
            node_id = int(inserted.lastrowid)
            node_id_by_upstream[upstream_id] = node_id
            if node_type in KNOWLEDGE_POINT_TYPES:
                seen_aliases = set()
                for alias in [str(node["name"]).strip(), *aliases]:
                    normalized = normalize_alias(alias)
                    if not normalized or normalized in seen_aliases:
                        continue
                    seen_aliases.add(normalized)
                    conn.execute(
                        """
                        INSERT INTO curriculum_node_aliases (
                            version_id, node_id, subject_key, book_upstream_id,
                            alias, normalized_alias, source
                        ) VALUES (?, ?, 'math', ?, ?, ?, ?)
                        """,
                        (
                            version_id,
                            node_id,
                            book_upstream_id,
                            alias,
                            normalized,
                            "canonical" if alias == str(node["name"]).strip() else "upstream",
                        ),
                    )
            if fail_after_nodes is not None and index >= int(fail_after_nodes):
                raise RuntimeError("injected curriculum import failure")
        for edge in bundle["edges"]:
            conn.execute(
                """
                INSERT INTO curriculum_edges (
                    version_id, source_node_id, target_node_id, relation_type,
                    source_properties_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    node_id_by_upstream[str(edge["source"])],
                    node_id_by_upstream[str(edge["target"])],
                    str(edge["type"]),
                    canonical_json(edge.get("properties") or {}),
                ),
            )
        for legacy_key, upstream_id in LEGACY_KNOWLEDGE_POINT_TARGETS.items():
            target_node_id = node_id_by_upstream.get(upstream_id)
            if not target_node_id:
                raise CurriculumValidationError("legacy knowledge point target is missing")
            conn.execute(
                """
                INSERT INTO curriculum_legacy_knowledge_point_map (
                    legacy_knowledge_point_key, version_id,
                    curriculum_node_id, mapping_note
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    legacy_key,
                    version_id,
                    int(target_node_id),
                    "Compatibility mapping for pre-curriculum learning events",
                ),
            )
        _materialize_book_membership(conn, version_id)
        _audit(
            conn,
            action="import",
            target_type="curriculum_version",
            target_key=CURRICULUM_VERSION_KEY,
            actor_user_id=actor_user_id,
            package_id=int(package["id"]),
            version_id=version_id,
            after={**stats, "source_revision": SOURCE_DATASET_REVISION, "source_sha256": SOURCE_SHA256},
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise
    version = conn.execute("SELECT * FROM curriculum_versions WHERE id=?", (version_id,)).fetchone()
    return {"changed": True, "version": dict(version), **stats}


def get_curriculum_version(conn: sqlite3.Connection, version_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT version.*, package.package_key, package.curriculum_name,
               package.subject_key, package.publisher_name, package.edition_name
        FROM curriculum_versions AS version
        JOIN curriculum_packages AS package ON package.id=version.package_id
        WHERE version.id=?
        """,
        (int(version_id),),
    ).fetchone()
    return dict(row) if row else None


def list_curriculum_versions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT version.*, package.package_key, package.curriculum_name,
               package.subject_key, package.publisher_name, package.edition_name
        FROM curriculum_versions AS version
        JOIN curriculum_packages AS package ON package.id=version.package_id
        ORDER BY version.registry_version DESC, version.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def diff_curriculum_versions(
    conn: sqlite3.Connection,
    from_version_id: int,
    to_version_id: int,
) -> dict:
    before = get_curriculum_version(conn, from_version_id)
    after = get_curriculum_version(conn, to_version_id)
    if not before or not after or int(before["package_id"]) != int(after["package_id"]):
        raise LookupError("curriculum version not found")
    before_nodes = {
        str(row["node_key"]): (str(row["canonical_name"]), str(row["node_type"]))
        for row in conn.execute(
            "SELECT node_key, canonical_name, node_type FROM curriculum_nodes WHERE version_id=?",
            (int(from_version_id),),
        ).fetchall()
    }
    after_nodes = {
        str(row["node_key"]): (str(row["canonical_name"]), str(row["node_type"]))
        for row in conn.execute(
            "SELECT node_key, canonical_name, node_type FROM curriculum_nodes WHERE version_id=?",
            (int(to_version_id),),
        ).fetchall()
    }
    def edge_keys(version_id: int) -> set[tuple[str, str, str]]:
        return {
            (str(row["source_key"]), str(row["target_key"]), str(row["relation_type"]))
            for row in conn.execute(
                """
                SELECT source.node_key AS source_key, target.node_key AS target_key,
                       edge.relation_type
                FROM curriculum_edges edge
                JOIN curriculum_nodes source ON source.id=edge.source_node_id
                JOIN curriculum_nodes target ON target.id=edge.target_node_id
                WHERE edge.version_id=?
                """,
                (int(version_id),),
            ).fetchall()
        }
    before_edges = edge_keys(from_version_id)
    after_edges = edge_keys(to_version_id)
    shared_keys = set(before_nodes).intersection(after_nodes)
    changed = sorted(key for key in shared_keys if before_nodes[key] != after_nodes[key])
    return {
        "from_version": before,
        "to_version": after,
        "nodes": {
            "added": sorted(set(after_nodes).difference(before_nodes)),
            "removed": sorted(set(before_nodes).difference(after_nodes)),
            "changed": changed,
        },
        "edges": {
            "added_count": len(after_edges.difference(before_edges)),
            "removed_count": len(before_edges.difference(after_edges)),
        },
    }


def list_curriculum_audit_events(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    include_global: bool = False,
    limit: int = 200,
) -> list[dict]:
    if include_global:
        rows = conn.execute(
            """
            SELECT * FROM curriculum_audit_events
            WHERE organization_id=? OR organization_id IS NULL
            ORDER BY id DESC LIMIT ?
            """,
            (int(organization_id), max(1, min(int(limit), 500))),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM curriculum_audit_events
            WHERE organization_id=?
            ORDER BY id DESC LIMIT ?
            """,
            (int(organization_id), max(1, min(int(limit), 500))),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["before"] = _json_mapping(item.pop("before_json", "{}"), label="audit before")
        item["after"] = _json_mapping(item.pop("after_json", "{}"), label="audit after")
        result.append(item)
    return result


def list_organization_knowledge_point_proposals(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    status: str = "proposed",
) -> list[dict]:
    conditions = ["proposal.organization_id=?"]
    params: list[object] = [int(organization_id)]
    if status != "all":
        if status not in {"proposed", "reviewed", "active", "rejected", "deprecated"}:
            raise CurriculumValidationError("proposal status is invalid")
        conditions.append("proposal.status=?")
        params.append(status)
    rows = conn.execute(
        f"""
        SELECT proposal.*, version.version_key, version.registry_version,
               book.canonical_name AS book_name, book.upstream_id AS book_upstream_id
        FROM curriculum_organization_knowledge_points proposal
        JOIN curriculum_versions version ON version.id=proposal.version_id
        JOIN curriculum_nodes book ON book.id=proposal.book_node_id
        WHERE {' AND '.join(conditions)}
        ORDER BY proposal.proposed_at DESC, proposal.id DESC
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def review_organization_knowledge_point_proposal(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    proposal_id: int,
    actor_user_id: int,
    request_id: str,
    approve: bool,
    note: str = "",
) -> dict:
    request_id = str(request_id or "").strip()
    if not request_id:
        raise CurriculumValidationError("proposal review request_id is required")
    payload = {
        "proposal_id": int(proposal_id),
        "approve": bool(approve),
        "note": str(note or ""),
    }
    payload_hash = content_hash(payload)
    replay = conn.execute(
        "SELECT * FROM curriculum_mapping_actions WHERE organization_id=? AND request_id=?",
        (int(organization_id), request_id),
    ).fetchone()
    if replay:
        replay_payload = _json_mapping(replay["payload_json"], label="mapping action")
        if str(replay_payload.get("payload_hash") or "") != payload_hash:
            raise CurriculumConflictError("proposal review request replay differs")
        proposal = conn.execute(
            "SELECT * FROM curriculum_organization_knowledge_points WHERE id=? AND organization_id=?",
            (int(proposal_id), int(organization_id)),
        ).fetchone()
        return {"proposal": dict(proposal) if proposal else None, "action": dict(replay), "replayed": True}
    proposal = conn.execute(
        "SELECT * FROM curriculum_organization_knowledge_points WHERE id=? AND organization_id=?",
        (int(proposal_id), int(organization_id)),
    ).fetchone()
    if not proposal:
        raise LookupError("knowledge point proposal not found")
    desired_status = "active" if approve else "rejected"
    if str(proposal["status"]) not in {"proposed", desired_status}:
        raise CurriculumConflictError("knowledge point proposal was already reviewed")
    now = _utc_now()
    if approve and str(proposal["status"]) != "active":
        normalized = normalize_alias(proposal["canonical_name"])
        base_conflict = conn.execute(
            """
            SELECT 1 FROM curriculum_node_aliases alias
            JOIN curriculum_book_nodes membership ON membership.node_id=alias.node_id
              AND membership.version_id=alias.version_id
            WHERE alias.version_id=? AND membership.book_node_id=?
              AND alias.subject_key=? AND alias.normalized_alias=? LIMIT 1
            """,
            (
                int(proposal["version_id"]), int(proposal["book_node_id"]),
                str(proposal["subject_key"]), normalized,
            ),
        ).fetchone()
        if base_conflict:
            raise CurriculumConflictError("proposal name conflicts with an existing knowledge point")
        conn.execute(
            """
            INSERT INTO curriculum_organization_aliases (
                organization_id, version_id, book_node_id, subject_key,
                organization_knowledge_point_id, alias, normalized_alias,
                status, created_by_user_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                int(organization_id), int(proposal["version_id"]),
                int(proposal["book_node_id"]), str(proposal["subject_key"]),
                int(proposal["id"]), str(proposal["canonical_name"]), normalized,
                int(actor_user_id), now,
            ),
        )
    conn.execute(
        """
        UPDATE curriculum_organization_knowledge_points
        SET status=?, reviewed_by_user_id=?, reviewed_at=?
        WHERE id=?
        """,
        (desired_status, int(actor_user_id), now, int(proposal_id)),
    )
    action_type = "approve_proposal" if approve else "reject_proposal"
    cursor = conn.execute(
        """
        INSERT INTO curriculum_mapping_actions (
            organization_id, candidate_id, request_id, action_type, status,
            proposed_name, note, actor_user_id, reviewed_by_user_id,
            payload_json, created_at, reviewed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(organization_id), f"proposal:{int(proposal_id)}", request_id,
            action_type, "approved" if approve else "rejected",
            str(proposal["canonical_name"]), str(note or ""), int(actor_user_id),
            int(actor_user_id), canonical_json({**payload, "payload_hash": payload_hash}),
            now, now,
        ),
    )
    after = conn.execute(
        "SELECT * FROM curriculum_organization_knowledge_points WHERE id=?",
        (int(proposal_id),),
    ).fetchone()
    _audit(
        conn,
        action=action_type,
        target_type="organization_knowledge_point",
        target_key=str(proposal["knowledge_point_key"]),
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        version_id=int(proposal["version_id"]),
        before=dict(proposal),
        after=dict(after),
        note=note,
    )
    action_row = conn.execute(
        "SELECT * FROM curriculum_mapping_actions WHERE id=?", (int(cursor.lastrowid),)
    ).fetchone()
    return {"proposal": dict(after), "action": dict(action_row), "replayed": False}


def review_curriculum_version(conn: sqlite3.Connection, version_id: int, *, actor_user_id: int) -> dict:
    version = get_curriculum_version(conn, version_id)
    if not version:
        raise LookupError("curriculum version not found")
    if version["status"] not in {"draft", "reviewed"}:
        raise CurriculumConflictError("only a draft version can be reviewed")
    verify_installed_curriculum(conn, version_id)
    now = _utc_now()
    conn.execute(
        """
        UPDATE curriculum_versions
        SET status='reviewed', reviewed_at=COALESCE(reviewed_at, ?),
            reviewed_by_user_id=COALESCE(reviewed_by_user_id, ?), updated_at=?
        WHERE id=?
        """,
        (now, int(actor_user_id), now, int(version_id)),
    )
    after = get_curriculum_version(conn, version_id)
    _audit(
        conn,
        action="review",
        target_type="curriculum_version",
        target_key=str(version["version_key"]),
        actor_user_id=actor_user_id,
        package_id=int(version["package_id"]),
        version_id=int(version_id),
        before=version,
        after=after,
    )
    return after


def activate_curriculum_version(conn: sqlite3.Connection, version_id: int, *, actor_user_id: int) -> dict:
    version = get_curriculum_version(conn, version_id)
    if not version:
        raise LookupError("curriculum version not found")
    if version["status"] not in {"reviewed", "active"}:
        raise CurriculumConflictError("curriculum version must be reviewed before activation")
    verify_installed_curriculum(conn, version_id)
    now = _utc_now()
    prior_rows = conn.execute(
        "SELECT * FROM curriculum_versions WHERE package_id=? AND status='active' AND id<>?",
        (int(version["package_id"]), int(version_id)),
    ).fetchall()
    conn.execute(
        """
        UPDATE curriculum_versions
        SET status='deprecated', deprecated_at=?, deprecated_by_user_id=?, updated_at=?
        WHERE package_id=? AND status='active' AND id<>?
        """,
        (now, int(actor_user_id), now, int(version["package_id"]), int(version_id)),
    )
    conn.execute(
        """
        UPDATE curriculum_versions
        SET status='active', activated_at=COALESCE(activated_at, ?),
            activated_by_user_id=COALESCE(activated_by_user_id, ?),
            deprecated_at=NULL, deprecated_by_user_id=NULL, updated_at=?
        WHERE id=?
        """,
        (now, int(actor_user_id), now, int(version_id)),
    )
    after = get_curriculum_version(conn, version_id)
    _audit(
        conn,
        action="activate",
        target_type="curriculum_version",
        target_key=str(version["version_key"]),
        actor_user_id=actor_user_id,
        package_id=int(version["package_id"]),
        version_id=int(version_id),
        before={"version": version, "prior_active": [dict(row) for row in prior_rows]},
        after=after,
    )
    return after


def rollback_curriculum_version(conn: sqlite3.Connection, target_version_id: int, *, actor_user_id: int) -> dict:
    target = get_curriculum_version(conn, target_version_id)
    if not target:
        raise LookupError("curriculum version not found")
    if not target.get("reviewed_at"):
        raise CurriculumConflictError("rollback target was never reviewed")
    verify_installed_curriculum(conn, target_version_id)
    before = [dict(row) for row in conn.execute(
        "SELECT * FROM curriculum_versions WHERE package_id=? ORDER BY id",
        (int(target["package_id"]),),
    ).fetchall()]
    now = _utc_now()
    conn.execute(
        """
        UPDATE curriculum_versions
        SET status=CASE WHEN id=? THEN 'active' ELSE 'deprecated' END,
            activated_at=CASE WHEN id=? THEN COALESCE(activated_at, ?) ELSE activated_at END,
            activated_by_user_id=CASE WHEN id=? THEN ? ELSE activated_by_user_id END,
            deprecated_at=CASE WHEN id=? THEN NULL ELSE COALESCE(deprecated_at, ?) END,
            deprecated_by_user_id=CASE WHEN id=? THEN NULL ELSE COALESCE(deprecated_by_user_id, ?) END,
            updated_at=?
        WHERE package_id=? AND status IN ('active','deprecated','reviewed')
        """,
        (
            int(target_version_id), int(target_version_id), now,
            int(target_version_id), int(actor_user_id),
            int(target_version_id), now,
            int(target_version_id), int(actor_user_id),
            now, int(target["package_id"]),
        ),
    )
    after = get_curriculum_version(conn, target_version_id)
    _audit(
        conn,
        action="rollback",
        target_type="curriculum_version",
        target_key=str(target["version_key"]),
        actor_user_id=actor_user_id,
        package_id=int(target["package_id"]),
        version_id=int(target_version_id),
        before=before,
        after=after,
    )
    return after


def get_active_curriculum_version(conn: sqlite3.Connection, subject_key: str = "math") -> Optional[dict]:
    row = conn.execute(
        """
        SELECT version.*, package.package_key, package.curriculum_name,
               package.subject_key, package.publisher_name, package.edition_name
        FROM curriculum_versions AS version
        JOIN curriculum_packages AS package ON package.id=version.package_id
        WHERE package.subject_key=? AND version.status='active'
        ORDER BY version.registry_version DESC LIMIT 1
        """,
        (str(subject_key).strip(),),
    ).fetchone()
    return dict(row) if row else None


def assign_curriculum_book(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    class_id: int,
    version_id: int,
    book_node_id: int,
    actor_user_id: int,
    request_id: str,
    expected_assignment_id: Optional[int],
    note: str = "",
) -> dict:
    """Backward-compatible single-book manual override."""
    request_id = str(request_id or "").strip()
    if not request_id:
        raise CurriculumValidationError("assignment request_id is required")
    legacy_payload_hash = content_hash(
        {
            "organization_id": int(organization_id),
            "class_id": int(class_id),
            "version_id": int(version_id),
            "book_node_id": int(book_node_id),
            "expected_assignment_id": int(expected_assignment_id or 0),
            "note": str(note or ""),
        }
    )
    _begin_immediate_if_needed(conn)
    receipt = conn.execute(
        """
        SELECT * FROM curriculum_assignment_requests
        WHERE organization_id=? AND request_id=?
        """,
        (int(organization_id), request_id),
    ).fetchone()
    if receipt:
        if str(receipt["payload_hash"] or "") != legacy_payload_hash:
            raise CurriculumConflictError("assignment request replay differs")
        if not receipt["assignment_id"]:
            raise CurriculumConflictError("assignment request receipt is incomplete")
        result = _json_mapping(receipt["result_json"], label="assignment receipt")
        if int(result.get("id") or 0) != int(receipt["assignment_id"]):
            raise CurriculumConflictError("assignment request result is unavailable")
        return result
    replay = conn.execute(
        "SELECT * FROM curriculum_class_assignments WHERE organization_id=? AND request_id=?",
        (int(organization_id), request_id),
    ).fetchone()
    if replay:
        if str(replay["payload_hash"] or "") != legacy_payload_hash:
            raise CurriculumConflictError("assignment request replay differs")
        result = serialize_class_assignment(conn, int(replay["id"]))
        if not result:
            raise CurriculumConflictError("assignment request result is unavailable")
        return result
    current_scope = get_effective_class_curriculum_scope(conn, class_id)
    expected_scope_token = str(current_scope.get("cas_token") or "")
    if expected_assignment_id is not None:
        active_ids = [
            int(item.get("assignment_id") or 0)
            for item in current_scope.get("books") or []
            if int(item.get("assignment_id") or 0)
        ]
        if active_ids != [int(expected_assignment_id)]:
            raise CurriculumConflictError("class curriculum assignment changed")
    elif current_scope.get("assignment_mode") == "manual":
        raise CurriculumConflictError("class curriculum assignment changed")
    scope = replace_class_curriculum_books(
        conn,
        organization_id=organization_id,
        class_id=class_id,
        version_id=version_id,
        book_node_ids=[book_node_id],
        primary_book_node_id=book_node_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        expected_cas_token=expected_scope_token,
        note=note,
        legacy_expected_assignment_id=expected_assignment_id,
        receipt_payload_hash=legacy_payload_hash,
    )
    primary = next(
        (item for item in scope["books"] if int(item["book_node_id"]) == int(book_node_id)),
        scope["books"][0],
    )
    return {**scope, **primary, "id": int(primary.get("assignment_id") or 0)}


def _normalized_grade_key(value: object) -> str:
    text = normalize_alias(value).replace(" ", "")
    chinese = "一二三四五六七八九"
    aliases = {
        **{f"{index}年级": f"grade_{index}" for index in range(1, 10)},
        **{f"{name}年级": f"grade_{index}" for index, name in enumerate(chinese, 1)},
        **{f"初{name}": f"grade_{index + 6}" for index, name in enumerate(chinese[:3], 1)},
        **{f"初{index}": f"grade_{index + 6}" for index in range(1, 4)},
    }
    return aliases.get(text, "")


def _grade_key_from_class_name(value: object) -> str:
    """Infer one unambiguous primary/junior grade from a structured class name."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    matches: set[str] = set()
    chinese_grades = {name: index for index, name in enumerate("一二三四五六七八九", 1)}
    for name, index in chinese_grades.items():
        if re.search(rf"{name}\s*年级", text):
            matches.add(f"grade_{index}")
    for value_match in re.finditer(r"(?<!\d)([1-9])\s*年级(?!\d)", text):
        matches.add(f"grade_{int(value_match.group(1))}")
    junior_grades = {"一": 7, "二": 8, "三": 9, "1": 7, "2": 8, "3": 9}
    for value_match in re.finditer(r"初\s*([一二三1-3])(?!\d)", text):
        matches.add(f"grade_{junior_grades[value_match.group(1)]}")
    return next(iter(matches)) if len(matches) == 1 else ""


def _scope_cas_payload(scope: Mapping[str, object]) -> dict:
    return {
        "schema_version": CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION,
        "class_id": int(scope.get("class_id") or 0),
        "organization_id": int(scope.get("organization_id") or 0),
        "subject_key": str(scope.get("subject_key") or ""),
        "assignment_mode": str(scope.get("assignment_mode") or "needs_review"),
        "inferred_grade_key": str(scope.get("inferred_grade_key") or ""),
        "version_id": int(scope.get("version_id") or 0),
        "book_node_ids": sorted(
            int(item.get("book_node_id") or 0)
            for item in scope.get("books") or []
            if isinstance(item, Mapping) and int(item.get("book_node_id") or 0)
        ),
        "assignment_ids": sorted(
            int(item.get("assignment_id") or 0)
            for item in scope.get("books") or []
            if isinstance(item, Mapping) and int(item.get("assignment_id") or 0)
        ),
        "primary_book_node_id": int(scope.get("primary_book_node_id") or 0),
    }


def _serialize_scope_book(
    conn: sqlite3.Connection,
    book_node_id: int,
    *,
    assignment_id: Optional[int] = None,
) -> dict:
    row = conn.execute(
        """
        SELECT book.id AS book_node_id, book.canonical_name AS book_name,
               book.upstream_id AS book_upstream_id, book.stage_key,
               book.grade_key, book.semester_key, book.version_id,
               (SELECT COUNT(DISTINCT membership.node_id)
                FROM curriculum_book_nodes membership
                JOIN curriculum_nodes kp ON kp.id=membership.node_id
                WHERE membership.version_id=book.version_id
                  AND membership.book_node_id=book.id
                  AND membership.membership_type='appears_in'
                  AND kp.node_type IN ('Concept','Skill')) AS knowledge_point_count
        FROM curriculum_nodes book
        WHERE book.id=? AND book.node_type='Book'
        """,
        (int(book_node_id),),
    ).fetchone()
    if not row:
        raise LookupError("curriculum book not found")
    return {**dict(row), "assignment_id": int(assignment_id or 0) or None}


def get_effective_class_curriculum_scope(
    conn: sqlite3.Connection,
    class_id: int,
) -> dict:
    class_row = conn.execute("SELECT * FROM classes WHERE id=?", (int(class_id),)).fetchone()
    if not class_row:
        raise LookupError("class not found")
    active_rows = conn.execute(
        """
        SELECT * FROM curriculum_class_assignments
        WHERE class_id=? AND status='active'
        ORDER BY is_primary DESC, id
        """,
        (int(class_id),),
    ).fetchall()
    mode = "manual" if active_rows else "needs_review"
    inference_source = ""
    inferred_grade = ""
    inferred_grade_key = ""
    version = None
    books: list[dict] = []
    reason = ""
    primary_book_node_id = 0
    if active_rows:
        version_ids = {int(row["version_id"]) for row in active_rows}
        if len(version_ids) != 1:
            raise CurriculumValidationError("class curriculum assignments span versions")
        version = get_curriculum_version(conn, next(iter(version_ids)))
        books = [
            _serialize_scope_book(
                conn,
                int(row["book_node_id"]),
                assignment_id=int(row["id"]),
            )
            for row in active_rows
        ]
        primary_book_node_id = int(active_rows[0]["book_node_id"])
        if str(version.get("status") or "") != "active":
            mode = "needs_review"
            reason = "原教材分配引用的课程版本已停用, 请重新确认教材范围"
    elif str(class_row["subject_key"] if "subject_key" in class_row.keys() else "") != "math":
        reason = "当前科目不支持自动匹配教材"
    else:
        class_columns = set(class_row.keys())
        current_grade = str(
            class_row["current_grade"] if "current_grade" in class_columns else ""
        ).strip()
        fallback_grade = str(class_row["grade"] if "grade" in class_columns else "").strip()
        inferred_grade_key = _normalized_grade_key(current_grade)
        if inferred_grade_key:
            inferred_grade = current_grade
            inference_source = "classes.current_grade"
        else:
            inferred_grade_key = _normalized_grade_key(fallback_grade)
            if inferred_grade_key:
                inferred_grade = fallback_grade
                inference_source = "classes.grade"
        if not inferred_grade_key:
            class_name = str(class_row["name"] or "").strip()
            inferred_grade_key = _grade_key_from_class_name(class_name)
            if inferred_grade_key:
                grade_number = int(inferred_grade_key.removeprefix("grade_"))
                inferred_grade = f"{'一二三四五六七八九'[grade_number - 1]}年级"
                inference_source = "classes.name"
        if not inferred_grade_key:
            reason = "班级年级无法安全识别, 请手动设置教材"
        else:
            version = get_active_curriculum_version(conn, subject_key="math")
            if not version:
                reason = "当前没有使用中的数学课程版本"
            else:
                rows = conn.execute(
                    """
                    SELECT id FROM curriculum_nodes
                    WHERE version_id=? AND node_type='Book' AND subject_key='math'
                      AND grade_key=? AND semester_key IN ('first','second')
                    ORDER BY CASE semester_key WHEN 'first' THEN 1 ELSE 2 END, id
                    """,
                    (int(version["id"]), inferred_grade_key),
                ).fetchall()
                if len(rows) != 2:
                    reason = "当前年级没有唯一的上下册组合, 请手动设置教材"
                else:
                    mode = "auto"
                    books = [_serialize_scope_book(conn, int(row["id"])) for row in rows]
                    primary_book_node_id = int(books[0]["book_node_id"])
    books.sort(
        key=lambda item: (
            {"first": 1, "second": 2, "required": 3, "selective_required": 4}.get(
                str(item.get("semester_key") or ""), 9
            ),
            int(item.get("book_node_id") or 0),
        )
    )
    scope = {
        "schema_version": CLASS_CURRICULUM_SCOPE_SCHEMA_VERSION,
        "class_id": int(class_row["id"]),
        "class_name": str(class_row["name"] or ""),
        "organization_id": int(class_row["organization_id"] or 0),
        "subject_key": str(
            class_row["subject_key"] if "subject_key" in class_row.keys() else ""
        ),
        "assignment_mode": mode,
        "inferred_grade": inferred_grade,
        "inferred_grade_key": inferred_grade_key,
        "inference_source": inference_source,
        "needs_review_reason": reason,
        "version_id": int(version["id"] if version else 0),
        "version_key": str(version["version_key"] if version else ""),
        "version_status": str(version["status"] if version else "draft"),
        "stable_registry_version": int(version["registry_version"] if version else 0),
        "content_hash": str(version["content_hash"] if version else ""),
        "package_key": str(version["package_key"] if version else ""),
        "curriculum_name": str(version["curriculum_name"] if version else ""),
        "publisher_name": str(version["publisher_name"] if version else ""),
        "edition_name": str(version["edition_name"] if version else ""),
        "source_dataset_revision": str(version["source_dataset_revision"] if version else ""),
        "source_sha256": str(version["source_sha256"] if version else ""),
        "books": books,
        "primary_book_node_id": primary_book_node_id or None,
    }
    scope["cas_token"] = content_hash(_scope_cas_payload(scope))
    scope["scope_hash"] = scope["cas_token"]
    primary_book = next(
        (
            item
            for item in books
            if int(item.get("book_node_id") or 0) == int(primary_book_node_id or 0)
        ),
        books[0] if books else {},
    )
    scope["id"] = int(primary_book.get("assignment_id") or 0)
    scope["book_node_id"] = int(primary_book.get("book_node_id") or 0)
    scope["book_name"] = str(primary_book.get("book_name") or "")
    scope["book_upstream_id"] = str(primary_book.get("book_upstream_id") or "")
    scope["stage_key"] = str(primary_book.get("stage_key") or "")
    scope["grade_key"] = str(primary_book.get("grade_key") or "")
    scope["semester_key"] = str(primary_book.get("semester_key") or "")
    scope["assignment_ids"] = [
        int(item["assignment_id"]) for item in books if item.get("assignment_id")
    ]
    scope["book_node_ids"] = [int(item["book_node_id"]) for item in books]
    return scope


def replace_class_curriculum_books(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    class_id: int,
    version_id: int,
    book_node_ids: Iterable[int],
    primary_book_node_id: Optional[int],
    actor_user_id: int,
    request_id: str,
    expected_cas_token: str,
    note: str = "",
    legacy_expected_assignment_id: Optional[int] = None,
    receipt_payload_hash: str = "",
) -> dict:
    request_id = str(request_id or "").strip()
    if not request_id:
        raise CurriculumValidationError("assignment request_id is required")
    normalized_book_ids = _normalized_positive_ids(book_node_ids, label="book_node_ids")
    if not normalized_book_ids:
        raise CurriculumValidationError("at least one curriculum book is required")
    try:
        primary_book_node_id = int(primary_book_node_id or normalized_book_ids[0])
    except (TypeError, ValueError) as exc:
        raise CurriculumValidationError("primary_book_node_id must be an integer") from exc
    if primary_book_node_id not in normalized_book_ids:
        raise CurriculumValidationError("primary book must be in the assigned book set")
    assignment_payload = {
        "organization_id": int(organization_id),
        "class_id": int(class_id),
        "version_id": int(version_id),
        "book_node_ids": normalized_book_ids,
        "primary_book_node_id": primary_book_node_id,
        "expected_cas_token": str(expected_cas_token or ""),
        "legacy_expected_assignment_id": int(legacy_expected_assignment_id or 0),
        "note": str(note or ""),
    }
    payload_hash = str(receipt_payload_hash or "") or content_hash(assignment_payload)
    _begin_immediate_if_needed(conn)
    receipt = conn.execute(
        """
        SELECT * FROM curriculum_assignment_requests
        WHERE organization_id=? AND request_id=?
        """,
        (int(organization_id), request_id),
    ).fetchone()
    if receipt:
        if str(receipt["payload_hash"] or "") != payload_hash:
            raise CurriculumConflictError("assignment request replay differs")
        result = _json_mapping(receipt["result_json"], label="assignment receipt")
        return result
    class_row = conn.execute(
        "SELECT id, organization_id, subject_key FROM classes WHERE id=?",
        (int(class_id),),
    ).fetchone()
    version = get_curriculum_version(conn, version_id)
    if not class_row or int(class_row["organization_id"] or 0) != int(organization_id):
        raise LookupError("class not found")
    placeholders = ",".join("?" for _ in normalized_book_ids)
    valid_books = conn.execute(
        f"""
        SELECT id FROM curriculum_nodes
        WHERE version_id=? AND node_type='Book' AND id IN ({placeholders})
        """,
        (int(version_id), *normalized_book_ids),
    ).fetchall()
    if not version or version["status"] != "active" or len(valid_books) != len(normalized_book_ids):
        raise CurriculumConflictError("only a book from the active version can be assigned")
    if str(class_row["subject_key"] or "") != str(version["subject_key"] or ""):
        raise CurriculumConflictError("class subject and curriculum subject differ")
    prior_scope = get_effective_class_curriculum_scope(conn, class_id)
    if str(prior_scope.get("cas_token") or "") != str(expected_cas_token or ""):
        raise CurriculumConflictError("class curriculum assignment changed")
    prior_ids = sorted(int(item["book_node_id"]) for item in prior_scope.get("books") or [])
    if (
        prior_scope.get("assignment_mode") == "manual"
        and prior_ids == normalized_book_ids
        and int(prior_scope.get("version_id") or 0) == int(version_id)
        and int(prior_scope.get("primary_book_node_id") or 0) == primary_book_node_id
    ):
        result = prior_scope
        conn.execute(
            """
            INSERT INTO curriculum_assignment_requests (
                organization_id, request_id, payload_hash, assignment_id,
                result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(organization_id), request_id, payload_hash,
                int((result.get("books") or [{}])[0].get("assignment_id") or 0) or None,
                canonical_json(result), _utc_now(),
            ),
        )
        return result
    now = _utc_now()
    conn.execute(
        "UPDATE curriculum_class_assignments SET status='superseded', ended_at=? WHERE class_id=? AND status='active'",
        (now, int(class_id)),
    )
    assignment_ids = []
    for book_node_id in normalized_book_ids:
        cursor = conn.execute(
            """
            INSERT INTO curriculum_class_assignments (
                organization_id, class_id, version_id, book_node_id, status,
                assigned_by_user_id, assigned_at, note, request_id, payload_hash,
                expected_previous_assignment_id, is_primary
            ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, '', ?, ?, ?)
            """,
            (
                int(organization_id), int(class_id), int(version_id), int(book_node_id),
                int(actor_user_id), now, str(note or ""), payload_hash,
                int(legacy_expected_assignment_id) if legacy_expected_assignment_id else None,
                1 if book_node_id == primary_book_node_id else 0,
            ),
        )
        assignment_ids.append(int(cursor.lastrowid))
    result = get_effective_class_curriculum_scope(conn, class_id)
    conn.execute(
        """
        INSERT INTO curriculum_assignment_requests (
            organization_id, request_id, payload_hash, assignment_id,
            result_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(organization_id), request_id, payload_hash, assignment_ids[0],
            canonical_json(result), now,
        ),
    )
    _audit(
        conn,
        action="assign",
        target_type="class_curriculum",
        target_key=str(class_id),
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        package_id=int(version["package_id"]),
        version_id=version_id,
        class_id=class_id,
        before=prior_scope,
        after=result,
        note=note,
    )
    return result


def reset_class_curriculum_to_auto(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    class_id: int,
    actor_user_id: int,
    request_id: str,
    expected_cas_token: str,
    note: str = "",
) -> dict:
    request_id = str(request_id or "").strip()
    if not request_id:
        raise CurriculumValidationError("assignment request_id is required")
    payload = {
        "organization_id": int(organization_id),
        "class_id": int(class_id),
        "assignment_mode": "auto",
        "expected_cas_token": str(expected_cas_token or ""),
        "note": str(note or ""),
    }
    payload_hash = content_hash(payload)
    _begin_immediate_if_needed(conn)
    receipt = conn.execute(
        "SELECT * FROM curriculum_assignment_requests WHERE organization_id=? AND request_id=?",
        (int(organization_id), request_id),
    ).fetchone()
    if receipt:
        if str(receipt["payload_hash"] or "") != payload_hash:
            raise CurriculumConflictError("assignment request replay differs")
        return _json_mapping(receipt["result_json"], label="assignment receipt")
    before = get_effective_class_curriculum_scope(conn, class_id)
    if int(before["organization_id"]) != int(organization_id):
        raise LookupError("class not found")
    if str(before.get("cas_token") or "") != str(expected_cas_token or ""):
        raise CurriculumConflictError("class curriculum assignment changed")
    now = _utc_now()
    conn.execute(
        "UPDATE curriculum_class_assignments SET status='removed', ended_at=? WHERE class_id=? AND status='active'",
        (now, int(class_id)),
    )
    result = get_effective_class_curriculum_scope(conn, class_id)
    conn.execute(
        """
        INSERT INTO curriculum_assignment_requests (
            organization_id, request_id, payload_hash, assignment_id, result_json, created_at
        ) VALUES (?, ?, ?, NULL, ?, ?)
        """,
        (int(organization_id), request_id, payload_hash, canonical_json(result), now),
    )
    _audit(
        conn,
        action="reset_auto",
        target_type="class_curriculum",
        target_key=str(class_id),
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        class_id=class_id,
        before=before,
        after=result,
        note=note,
    )
    return result


def serialize_class_assignment(conn: sqlite3.Connection, assignment_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT assignment.*, class.name AS class_name, class.subject_key,
               version.version_key, version.registry_version AS stable_registry_version,
               version.source_dataset_revision, version.source_sha256,
               version.content_hash,
               version.status AS version_status, package.package_key,
               package.curriculum_name, package.publisher_name, package.edition_name,
               book.canonical_name AS book_name, book.upstream_id AS book_upstream_id,
               book.stage_key, book.grade_key, book.semester_key
        FROM curriculum_class_assignments AS assignment
        JOIN classes AS class ON class.id=assignment.class_id
        JOIN curriculum_versions AS version ON version.id=assignment.version_id
        JOIN curriculum_packages AS package ON package.id=version.package_id
        JOIN curriculum_nodes AS book ON book.id=assignment.book_node_id
        WHERE assignment.id=?
        """,
        (int(assignment_id),),
    ).fetchone()
    return dict(row) if row else None


def get_class_curriculum_assignment(conn: sqlite3.Connection, class_id: int) -> Optional[dict]:
    scope = get_effective_class_curriculum_scope(conn, class_id)
    books = scope.get("books") or []
    if not books:
        return None
    primary_id = int(scope.get("primary_book_node_id") or books[0]["book_node_id"])
    primary = next(
        (item for item in books if int(item["book_node_id"]) == primary_id), books[0]
    )
    return {
        **scope,
        **primary,
        "id": int(primary.get("assignment_id") or 0),
        "book_node_ids": [int(item["book_node_id"]) for item in books],
        "assignment_ids": [
            int(item["assignment_id"]) for item in books if item.get("assignment_id")
        ],
    }


def list_curriculum_books(conn: sqlite3.Connection, version_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT node.*,
               (SELECT COUNT(*) FROM curriculum_book_nodes AS membership
                JOIN curriculum_nodes AS kp ON kp.id=membership.node_id
                WHERE membership.version_id=node.version_id
                  AND membership.book_node_id=node.id
                  AND membership.membership_type='appears_in'
                  AND kp.node_type IN ('Concept','Skill')) AS knowledge_point_count
        FROM curriculum_nodes AS node
        WHERE node.version_id=? AND node.node_type='Book'
        ORDER BY CASE node.stage_key WHEN 'primary' THEN 1 WHEN 'junior' THEN 2 ELSE 3 END,
                 node.upstream_id
        """,
        (int(version_id),),
    ).fetchall()
    return [dict(row) for row in rows]


def _parse_json_list(value: object) -> list:
    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def list_curriculum_nodes(
    conn: sqlite3.Connection,
    *,
    version_id: int,
    stage_key: str = "",
    grade_key: str = "",
    book_upstream_id: str = "",
    chapter_upstream_id: str = "",
    query: str = "",
    node_type: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 100))
    conditions = ["node.version_id=?"]
    params: list[object] = [int(version_id)]
    if stage_key:
        conditions.append("node.stage_key=?")
        params.append(str(stage_key))
    if grade_key:
        conditions.append("node.grade_key=?")
        params.append(str(grade_key))
    if book_upstream_id:
        conditions.append(
            """EXISTS (
                SELECT 1 FROM curriculum_book_nodes membership
                JOIN curriculum_nodes book ON book.id=membership.book_node_id
                WHERE membership.version_id=node.version_id
                  AND membership.node_id=node.id AND book.upstream_id=?
            )"""
        )
        params.append(str(book_upstream_id))
    if node_type:
        conditions.append("node.node_type=?")
        params.append(str(node_type))
    else:
        conditions.append("node.node_type IN ('Book','Chapter','Section','Concept','Skill')")
    if chapter_upstream_id:
        conditions.append(
            """(
                node.upstream_id=? OR EXISTS (
                    SELECT 1 FROM curriculum_edges edge
                    JOIN curriculum_nodes chapter ON chapter.id=edge.target_node_id
                    WHERE edge.version_id=node.version_id AND edge.source_node_id=node.id
                      AND edge.relation_type='appears_in' AND chapter.upstream_id=?
                ) OR EXISTS (
                    SELECT 1 FROM curriculum_edges section_edge
                    JOIN curriculum_nodes section ON section.id=section_edge.target_node_id
                    JOIN curriculum_edges chapter_edge ON chapter_edge.source_node_id=section.id
                    JOIN curriculum_nodes chapter ON chapter.id=chapter_edge.target_node_id
                    WHERE section_edge.version_id=node.version_id
                      AND section_edge.source_node_id=node.id
                      AND section_edge.relation_type='appears_in'
                      AND chapter_edge.relation_type='is_part_of'
                      AND chapter.upstream_id=?
                )
            )"""
        )
        params.extend([chapter_upstream_id, chapter_upstream_id, chapter_upstream_id])
    normalized_query = normalize_alias(query)
    if normalized_query:
        conditions.append(
            """(
                instr(lower(node.canonical_name), lower(?))>0 OR EXISTS (
                    SELECT 1 FROM curriculum_node_aliases alias
                    WHERE alias.node_id=node.id AND instr(alias.normalized_alias, ?)>0
                )
            )"""
        )
        params.extend([str(query).strip(), normalized_query])
    where_sql = " AND ".join(conditions)
    total = int(conn.execute(f"SELECT COUNT(*) FROM curriculum_nodes node WHERE {where_sql}", params).fetchone()[0])
    rows = conn.execute(
        f"""
        SELECT node.* FROM curriculum_nodes node
        WHERE {where_sql}
        ORDER BY CASE node.node_type WHEN 'Book' THEN 1 WHEN 'Chapter' THEN 2
                 WHEN 'Section' THEN 3 WHEN 'Concept' THEN 4 ELSE 5 END,
                 node.book_upstream_id, node.upstream_id
        LIMIT ? OFFSET ?
        """,
        (*params, page_size, (page - 1) * page_size),
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["aliases"] = _parse_json_list(item.pop("aliases_json", "[]"))
        item.pop("source_properties_json", None)
        items.append(item)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def _node_path(
    conn: sqlite3.Connection,
    node: Mapping[str, object],
    *,
    book_node_id: Optional[int] = None,
) -> list[dict]:
    if node["node_type"] == "Book":
        return [{"node_key": node["node_key"], "node_type": "Book", "name": node["canonical_name"]}]
    path_nodes = []
    current_id = int(node["id"])
    visited = set()
    while current_id not in visited:
        visited.add(current_id)
        current = conn.execute("SELECT * FROM curriculum_nodes WHERE id=?", (current_id,)).fetchone()
        if not current:
            break
        path_nodes.append({"node_key": current["node_key"], "node_type": current["node_type"], "name": current["canonical_name"]})
        parent = conn.execute(
            """
            SELECT parent.id FROM curriculum_edges edge
            JOIN curriculum_nodes parent ON parent.id=edge.target_node_id
            WHERE edge.source_node_id=? AND edge.relation_type IN ('is_part_of','appears_in')
              AND parent.node_type IN ('Book','Chapter','Section')
              AND (?=0 OR EXISTS (
                  SELECT 1 FROM curriculum_book_nodes membership
                  WHERE membership.version_id=edge.version_id
                    AND membership.book_node_id=? AND membership.node_id=parent.id
              ))
            ORDER BY CASE parent.node_type WHEN 'Section' THEN 1 WHEN 'Chapter' THEN 2 ELSE 3 END
            LIMIT 1
            """,
            (current_id, int(book_node_id or 0), int(book_node_id or 0)),
        ).fetchone()
        if not parent:
            break
        current_id = int(parent["id"])
    return list(reversed(path_nodes))


def get_curriculum_node_detail(
    conn: sqlite3.Connection,
    node_id: int,
    *,
    book_node_id: Optional[int] = None,
) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT node.*, version.version_key, version.source_dataset_revision,
               version.source_sha256, version.status AS version_status,
               version.data_license, package.package_key, package.curriculum_name,
               package.publisher_name, package.edition_name
        FROM curriculum_nodes node
        JOIN curriculum_versions version ON version.id=node.version_id
        JOIN curriculum_packages package ON package.id=version.package_id
        WHERE node.id=?
        """,
        (int(node_id),),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["aliases"] = _parse_json_list(result.pop("aliases_json", "[]"))
    result.pop("source_properties_json", None)
    result["path"] = _node_path(conn, result, book_node_id=book_node_id)
    relations = {}
    for relation_type, direction, label in (
        ("prerequisites_for", "incoming", "prerequisites"),
        ("prerequisites_for", "outgoing", "follow_ups"),
        ("relates_to", "both", "related"),
        ("is_a", "both", "is_a"),
    ):
        if direction == "incoming":
            sql = "edge.target_node_id=?"
            joined = "related.id=edge.source_node_id"
        elif direction == "outgoing":
            sql = "edge.source_node_id=?"
            joined = "related.id=edge.target_node_id"
        else:
            sql = "(edge.source_node_id=? OR edge.target_node_id=?)"
            joined = "related.id=CASE WHEN edge.source_node_id=? THEN edge.target_node_id ELSE edge.source_node_id END"
        if direction == "both":
            rows = conn.execute(
                f"""SELECT related.id, related.node_key, related.node_type, related.canonical_name
                    FROM curriculum_edges edge JOIN curriculum_nodes related ON {joined}
                    WHERE edge.relation_type=? AND {sql}
                    ORDER BY related.canonical_name LIMIT 100""",
                (relation_type, int(node_id), int(node_id), int(node_id)),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT related.id, related.node_key, related.node_type, related.canonical_name
                    FROM curriculum_edges edge JOIN curriculum_nodes related ON {joined}
                    WHERE edge.relation_type=? AND {sql}
                    ORDER BY related.canonical_name LIMIT 100""",
                (relation_type, int(node_id)),
            ).fetchall()
        relations[label] = [dict(item) for item in rows]
    result["relations"] = relations
    return result


def get_extraction_registry(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    class_id: int,
    subject_key: str,
    limit: int = 320,
) -> dict:
    assignment = get_class_curriculum_assignment(conn, class_id)
    if not assignment:
        prior_assignment = conn.execute(
            "SELECT 1 FROM curriculum_class_assignments WHERE class_id=? LIMIT 1",
            (int(class_id),),
        ).fetchone()
        if prior_assignment:
            raise CurriculumValidationError("class curriculum assignment requires review")
        return {"assignment": None, "registry": []}
    if (
        int(assignment["organization_id"]) != int(organization_id)
        or str(assignment["subject_key"] or "") != str(subject_key)
        or str(assignment["version_status"] or "") != "active"
    ):
        raise CurriculumValidationError("class curriculum assignment scope is invalid")
    book_ids = sorted({int(value) for value in assignment.get("book_node_ids") or []})
    if not book_ids:
        book_ids = [int(assignment["book_node_id"])]
    placeholders = ",".join("?" for _ in book_ids)
    base_registry_count = int(conn.execute(
        f"""
        SELECT COUNT(DISTINCT node.id) FROM curriculum_book_nodes membership
        JOIN curriculum_nodes node ON node.id=membership.node_id
        WHERE membership.version_id=? AND membership.book_node_id IN ({placeholders})
          AND membership.membership_type='appears_in'
          AND node.node_type IN ('Concept','Skill')
        """,
        (int(assignment["version_id"]), *book_ids),
    ).fetchone()[0])
    custom_registry_count = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM curriculum_organization_knowledge_points
            WHERE organization_id=? AND version_id=? AND book_node_id IN (""" + placeholders + """)
              AND subject_key=? AND status='active'
            """,
            (
                int(organization_id), int(assignment["version_id"]),
                *book_ids, str(subject_key),
            ),
        ).fetchone()[0]
    )
    registry_count = base_registry_count + custom_registry_count
    effective_limit = max(1, min(int(limit), 500))
    if registry_count > effective_limit:
        raise CurriculumValidationError("assigned book registry exceeds the frozen prompt limit")
    rows = conn.execute(
        """
        SELECT DISTINCT node.* FROM curriculum_book_nodes membership
        JOIN curriculum_nodes node ON node.id=membership.node_id
        WHERE membership.version_id=? AND membership.book_node_id IN (""" + placeholders + """)
          AND membership.membership_type='appears_in'
          AND node.node_type IN ('Concept','Skill')
        ORDER BY node.upstream_id LIMIT ?
        """,
        (int(assignment["version_id"]), *book_ids, effective_limit),
    ).fetchall()
    registry = []
    for row in rows:
        aliases = conn.execute(
            "SELECT alias FROM curriculum_node_aliases WHERE node_id=? ORDER BY id",
            (int(row["id"]),),
        ).fetchall()
        org_aliases = conn.execute(
            """
            SELECT alias FROM curriculum_organization_aliases
            WHERE organization_id=? AND curriculum_node_id=? AND status='active'
            ORDER BY id
            """,
            (int(organization_id), int(row["id"])),
        ).fetchall()
        legacy_aliases = conn.execute(
            """
            SELECT legacy_knowledge_point_key AS alias
            FROM curriculum_legacy_knowledge_point_map
            WHERE version_id=? AND curriculum_node_id=?
            ORDER BY legacy_knowledge_point_key
            """,
            (int(assignment["version_id"]), int(row["id"])),
        ).fetchall()
        memberships = conn.execute(
            f"""
            SELECT membership.book_node_id, book.upstream_id
            FROM curriculum_book_nodes membership
            JOIN curriculum_nodes book ON book.id=membership.book_node_id
            WHERE membership.version_id=? AND membership.node_id=?
              AND membership.book_node_id IN ({placeholders})
              AND membership.membership_type='appears_in'
            ORDER BY membership.book_node_id
            """,
            (int(assignment["version_id"]), int(row["id"]), *book_ids),
        ).fetchall()
        item_book_ids = [int(item["book_node_id"]) for item in memberships]
        preferred_book_id = item_book_ids[0]
        path = _node_path(conn, dict(row), book_node_id=preferred_book_id)
        registry.append(
            {
                "knowledge_point_key": str(row["node_key"]),
                "subject_key": str(row["subject_key"]),
                "canonical_name": str(row["canonical_name"]),
                "parent_key": path[-2]["node_key"] if len(path) >= 2 else None,
                "registry_version": int(assignment["stable_registry_version"]),
                "aliases": list(
                    dict.fromkeys(
                        str(item["alias"])
                        for item in [*aliases, *org_aliases, *legacy_aliases]
                    )
                ),
                "curriculum_node_id": int(row["id"]),
                "curriculum_version_id": int(assignment["version_id"]),
                "book_upstream_id": str(memberships[0]["upstream_id"]),
                "book_node_id": preferred_book_id,
                "curriculum_book_node_ids": item_book_ids,
                "knowledge_point_kind": str(row["node_type"]),
                "curriculum_path": path,
                "node_content_hash": content_hash(
                    {
                        "node_key": row["node_key"],
                        "canonical_name": row["canonical_name"],
                        "aliases": [str(item["alias"]) for item in aliases],
                        "description": row["description"],
                        "importance": row["importance"],
                        "source_locator": row["source_locator"],
                    }
                ),
            }
        )
    custom_rows = conn.execute(
        """
        SELECT * FROM curriculum_organization_knowledge_points
        WHERE organization_id=? AND version_id=? AND book_node_id IN (""" + placeholders + """)
          AND subject_key=? AND status='active'
        ORDER BY knowledge_point_key
        """,
        (
            int(organization_id), int(assignment["version_id"]), *book_ids, str(subject_key),
        ),
    ).fetchall()
    for row in custom_rows:
        custom_book_id = int(row["book_node_id"])
        book = conn.execute(
            "SELECT * FROM curriculum_nodes WHERE id=? AND node_type='Book'",
            (custom_book_id,),
        ).fetchone()
        book_path = _node_path(conn, dict(book), book_node_id=custom_book_id) if book else []
        aliases = conn.execute(
            """
            SELECT alias FROM curriculum_organization_aliases
            WHERE organization_id=? AND organization_knowledge_point_id=?
              AND status='active' ORDER BY id
            """,
            (int(organization_id), int(row["id"])),
        ).fetchall()
        alias_values = list(
            dict.fromkeys([str(row["canonical_name"]), *(str(item["alias"]) for item in aliases)])
        )
        registry.append(
            {
                "knowledge_point_key": str(row["knowledge_point_key"]),
                "subject_key": str(row["subject_key"]),
                "canonical_name": str(row["canonical_name"]),
                "parent_key": book_path[-1]["node_key"] if book_path else None,
                "registry_version": int(assignment["stable_registry_version"]),
                "aliases": alias_values,
                "curriculum_node_id": 0,
                "organization_knowledge_point_id": int(row["id"]),
                "curriculum_version_id": int(assignment["version_id"]),
                "book_upstream_id": str(book["upstream_id"] if book else ""),
                "book_node_id": custom_book_id,
                "curriculum_book_node_ids": [custom_book_id],
                "knowledge_point_kind": "OrganizationKnowledgePoint",
                "curriculum_path": book_path,
                "node_content_hash": content_hash(
                    {
                        "knowledge_point_key": row["knowledge_point_key"],
                        "canonical_name": row["canonical_name"],
                        "description": row["description"],
                    }
                ),
            }
        )
    registry.sort(key=lambda item: str(item["knowledge_point_key"]))
    return {
        "assignment": assignment,
        "registry": registry,
        "registry_metadata": {"count": registry_count, "limit": effective_limit, "truncated": False},
    }


def resolve_curriculum_knowledge_point(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    class_id: int,
    subject_key: str,
    value: object,
) -> Optional[dict]:
    text = str(value or "").strip()
    if not text:
        return None
    assignment = get_class_curriculum_assignment(conn, class_id)
    if (
        not assignment
        or int(assignment["organization_id"]) != int(organization_id)
        or str(assignment["subject_key"] or "") != str(subject_key)
        or str(assignment["version_status"] or "") not in {"active", "deprecated"}
    ):
        return None
    book_ids = sorted({int(value) for value in assignment.get("book_node_ids") or []})
    if not book_ids:
        book_ids = [int(assignment["book_node_id"])]
    placeholders = ",".join("?" for _ in book_ids)
    direct = conn.execute(
        f"""
        SELECT DISTINCT node.* FROM curriculum_book_nodes membership
        JOIN curriculum_nodes node ON node.id=membership.node_id
        WHERE membership.version_id=? AND membership.book_node_id IN ({placeholders})
          AND membership.membership_type='appears_in' AND node.subject_key=?
          AND node.node_type IN ('Concept','Skill') AND node.node_key=?
        """,
        (int(assignment["version_id"]), *book_ids, str(subject_key), text),
    ).fetchone()
    if direct:
        result = dict(direct)
        memberships = conn.execute(
            f"""
            SELECT DISTINCT book_node_id FROM curriculum_book_nodes
            WHERE version_id=? AND node_id=? AND book_node_id IN ({placeholders})
              AND membership_type='appears_in' ORDER BY book_node_id
            """,
            (int(assignment["version_id"]), int(result["id"]), *book_ids),
        ).fetchall()
        result_book_ids = [int(row["book_node_id"]) for row in memberships]
        result["knowledge_point_key"] = result["node_key"]
        result["registry_version"] = int(assignment["stable_registry_version"])
        result["curriculum_node_id"] = int(result["id"])
        result["curriculum_version_id"] = int(assignment["version_id"])
        result["book_node_id"] = result_book_ids[0]
        result["curriculum_book_node_ids"] = result_book_ids
        result["curriculum_content_hash"] = str(assignment["content_hash"] or "")
        result["node_content_hash"] = content_hash(
            {
                "node_key": result["node_key"],
                "canonical_name": result["canonical_name"],
                "aliases": _parse_json_list(result["aliases_json"]),
                "description": result["description"],
                "importance": result["importance"],
                "source_locator": result["source_locator"],
            }
        )
        return result
    legacy = conn.execute(
        f"""
        SELECT node.* FROM curriculum_legacy_knowledge_point_map legacy
        JOIN curriculum_nodes node ON node.id=legacy.curriculum_node_id
        JOIN curriculum_book_nodes membership ON membership.node_id=node.id
          AND membership.version_id=legacy.version_id
        WHERE legacy.version_id=? AND legacy.legacy_knowledge_point_key=?
          AND membership.book_node_id IN ({placeholders})
          AND membership.membership_type='appears_in'
          AND node.subject_key=?
        """,
        (
            int(assignment["version_id"]),
            text,
            *book_ids,
            str(subject_key),
        ),
    ).fetchone()
    if legacy:
        result = dict(legacy)
        legacy_books = conn.execute(
            f"""
            SELECT DISTINCT book_node_id FROM curriculum_book_nodes
            WHERE version_id=? AND node_id=? AND book_node_id IN ({placeholders})
              AND membership_type='appears_in' ORDER BY book_node_id
            """,
            (int(assignment["version_id"]), int(result["id"]), *book_ids),
        ).fetchall()
        result_book_ids = [int(row["book_node_id"]) for row in legacy_books]
        result["knowledge_point_key"] = result["node_key"]
        result["registry_version"] = int(assignment["stable_registry_version"])
        result["curriculum_node_id"] = int(result["id"])
        result["curriculum_version_id"] = int(assignment["version_id"])
        result["book_node_id"] = result_book_ids[0]
        result["curriculum_book_node_ids"] = result_book_ids
        result["curriculum_content_hash"] = str(assignment["content_hash"] or "")
        result["node_content_hash"] = content_hash(
            {
                "node_key": result["node_key"],
                "canonical_name": result["canonical_name"],
                "aliases": _parse_json_list(result["aliases_json"]),
                "description": result["description"],
                "importance": result["importance"],
                "source_locator": result["source_locator"],
            }
        )
        return result
    normalized = normalize_alias(text)
    rows = conn.execute(
        f"""
        SELECT DISTINCT node.* FROM curriculum_node_aliases alias
        JOIN curriculum_nodes node ON node.id=alias.node_id
        JOIN curriculum_book_nodes membership ON membership.node_id=node.id
          AND membership.version_id=alias.version_id
        WHERE alias.version_id=? AND membership.book_node_id IN ({placeholders})
          AND membership.membership_type='appears_in' AND alias.subject_key=?
          AND alias.normalized_alias=?
        UNION
        SELECT DISTINCT node.* FROM curriculum_organization_aliases alias
        JOIN curriculum_nodes node ON node.id=alias.curriculum_node_id
        JOIN curriculum_book_nodes membership ON membership.node_id=node.id
          AND membership.version_id=alias.version_id
        WHERE alias.organization_id=? AND alias.version_id=? AND alias.book_node_id IN ({placeholders})
          AND membership.book_node_id=alias.book_node_id
          AND membership.membership_type='appears_in'
          AND alias.subject_key=? AND alias.normalized_alias=? AND alias.status='active'
        """,
        (
            int(assignment["version_id"]), *book_ids, str(subject_key), normalized,
            int(organization_id), int(assignment["version_id"]), *book_ids, str(subject_key), normalized,
        ),
    ).fetchall()
    if len(rows) != 1:
        return None
    result = dict(rows[0])
    matched_books = conn.execute(
        f"""
        SELECT DISTINCT book_node_id FROM curriculum_book_nodes
        WHERE version_id=? AND node_id=? AND book_node_id IN ({placeholders})
          AND membership_type='appears_in' ORDER BY book_node_id
        """,
        (int(assignment["version_id"]), int(result["id"]), *book_ids),
    ).fetchall()
    result_book_ids = [int(row["book_node_id"]) for row in matched_books]
    result["knowledge_point_key"] = result["node_key"]
    result["registry_version"] = int(assignment["stable_registry_version"])
    result["curriculum_node_id"] = int(result["id"])
    result["curriculum_version_id"] = int(assignment["version_id"])
    result["book_node_id"] = result_book_ids[0]
    result["curriculum_book_node_ids"] = result_book_ids
    result["curriculum_content_hash"] = str(assignment["content_hash"] or "")
    result["node_content_hash"] = content_hash(
        {
            "node_key": result["node_key"],
            "canonical_name": result["canonical_name"],
            "aliases": _parse_json_list(result["aliases_json"]),
            "description": result["description"],
            "importance": result["importance"],
            "source_locator": result["source_locator"],
        }
    )
    return result


def curriculum_context_for_knowledge_point(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    class_id: int,
    subject_key: str,
    knowledge_point_key: str,
) -> Optional[dict]:
    resolved = resolve_curriculum_knowledge_point(
        conn,
        organization_id=organization_id,
        class_id=class_id,
        subject_key=subject_key,
        value=knowledge_point_key,
    )
    if not resolved:
        return None
    assignment = get_class_curriculum_assignment(conn, class_id)
    if not assignment:
        return None
    detail = get_curriculum_node_detail(
        conn,
        int(resolved["id"]),
        book_node_id=int(assignment["book_node_id"]),
    )
    if not detail:
        return None
    return {
        "curriculum_node_id": int(detail["id"]),
        "knowledge_point_key": str(knowledge_point_key),
        "curriculum_knowledge_point_key": str(detail["node_key"]),
        "path": detail["path"],
        "prerequisites": detail["relations"]["prerequisites"],
        "follow_ups": detail["relations"]["follow_ups"],
        "related": detail["relations"]["related"],
        "source": {
            "package_key": detail["package_key"],
            "version_key": detail["version_key"],
            "dataset_revision": detail["source_dataset_revision"],
            "source_sha256": detail["source_sha256"],
            "license": detail["data_license"],
        },
    }


def curriculum_context_for_organization_knowledge_point(
    conn: sqlite3.Connection,
    *,
    organization_id: int,
    organization_knowledge_point_id: int,
    book_node_id: int,
) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT custom.*, version.version_key, version.source_dataset_revision,
               version.source_sha256, version.content_hash,
               version.data_license, package.package_key,
               book.node_key AS book_node_key, book.node_type AS book_node_type,
               book.canonical_name AS book_name
        FROM curriculum_organization_knowledge_points custom
        JOIN curriculum_versions version ON version.id=custom.version_id
        JOIN curriculum_packages package ON package.id=version.package_id
        JOIN curriculum_nodes book ON book.id=custom.book_node_id
        WHERE custom.id=? AND custom.organization_id=?
          AND custom.book_node_id=?
          AND custom.status IN ('active','deprecated')
        """,
        (
            int(organization_knowledge_point_id),
            int(organization_id),
            int(book_node_id),
        ),
    ).fetchone()
    if not row:
        return None
    book = conn.execute(
        "SELECT * FROM curriculum_nodes WHERE id=? AND node_type='Book'",
        (int(book_node_id),),
    ).fetchone()
    if not book:
        return None
    path = _node_path(conn, dict(book), book_node_id=int(book_node_id))
    path.append(
        {
            "node_key": str(row["knowledge_point_key"]),
            "node_type": "OrganizationKnowledgePoint",
            "name": str(row["canonical_name"]),
        }
    )
    return {
        "curriculum_node_id": None,
        "organization_knowledge_point_id": int(row["id"]),
        "knowledge_point_key": str(row["knowledge_point_key"]),
        "curriculum_knowledge_point_key": str(row["knowledge_point_key"]),
        "knowledge_point_kind": "OrganizationKnowledgePoint",
        "path": path,
        "prerequisites": [],
        "follow_ups": [],
        "related": [],
        "source": {
            "package_key": str(row["package_key"]),
            "version_key": str(row["version_key"]),
            "dataset_revision": str(row["source_dataset_revision"]),
            "source_sha256": str(row["source_sha256"]),
            "content_hash": str(row["content_hash"]),
            "license": str(row["data_license"]),
        },
    }


def build_semantica_curriculum_snapshot(conn: sqlite3.Connection) -> dict:
    """Return the complete reviewed curriculum graph from canonical SQLite."""
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='curriculum_versions'"
    ).fetchone():
        empty = {"nodes": [], "edges": []}
        return {
            "schema_version": "xingrun.semantica-curriculum.v1",
            **empty,
            "node_count": 0,
            "edge_count": 0,
            "content_hash": content_hash(empty),
        }
    version_rows = conn.execute(
        """
        SELECT version.*, package.package_key, package.subject_key,
               package.curriculum_name, package.publisher_name,
               package.edition_name
        FROM curriculum_versions version
        JOIN curriculum_packages package ON package.id=version.package_id
        WHERE version.status IN ('reviewed','active','deprecated')
        ORDER BY version.version_key
        """
    ).fetchall()
    version_ids = [int(row["id"]) for row in version_rows]
    if not version_ids:
        return {
            "schema_version": "xingrun.semantica-curriculum.v1",
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "content_hash": content_hash({"nodes": [], "edges": []}),
        }
    placeholders = ",".join("?" for _ in version_ids)
    version_by_id = {int(row["id"]): dict(row) for row in version_rows}
    node_rows = conn.execute(
        f"""
        SELECT * FROM curriculum_nodes
        WHERE version_id IN ({placeholders})
        ORDER BY version_id, upstream_id
        """,
        version_ids,
    ).fetchall()
    node_key_by_id = {int(row["id"]): str(row["node_key"]) for row in node_rows}
    nodes = []
    for row in node_rows:
        version = version_by_id[int(row["version_id"])]
        nodes.append(
            {
                "package_key": str(version["package_key"]),
                "version_key": str(version["version_key"]),
                "version_status": str(version["status"]),
                "subject_key": str(version["subject_key"]),
                "source_revision": str(version["source_dataset_revision"]),
                "source_sha256": str(version["source_sha256"]),
                "curriculum_content_hash": str(version["content_hash"]),
                "node_key": str(row["node_key"]),
                "node_type": str(row["node_type"]),
                "knowledge_point_kind": str(row["knowledge_point_kind"] or ""),
                "canonical_name": str(row["canonical_name"]),
                "description": str(row["description"] or ""),
                "importance": str(row["importance"] or ""),
                "stage_key": str(row["stage_key"]),
                "grade_key": str(row["grade_key"]),
                "semester_key": str(row["semester_key"]),
                "book_upstream_id": str(row["book_upstream_id"]),
            }
        )
    edge_rows = conn.execute(
        f"""
        SELECT * FROM curriculum_edges
        WHERE version_id IN ({placeholders})
        ORDER BY version_id, relation_type, source_node_id, target_node_id
        """,
        version_ids,
    ).fetchall()
    edges = []
    for row in edge_rows:
        version = version_by_id[int(row["version_id"])]
        source_key = node_key_by_id.get(int(row["source_node_id"]))
        target_key = node_key_by_id.get(int(row["target_node_id"]))
        if not source_key or not target_key:
            raise CurriculumValidationError("curriculum graph edge endpoint is missing")
        edges.append(
            {
                "package_key": str(version["package_key"]),
                "version_key": str(version["version_key"]),
                "subject_key": str(version["subject_key"]),
                "source_node_key": source_key,
                "target_node_key": target_key,
                "relation_type": str(row["relation_type"]),
            }
        )
    graph_content = {"nodes": nodes, "edges": edges}
    return {
        "schema_version": "xingrun.semantica-curriculum.v1",
        **graph_content,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "content_hash": content_hash(graph_content),
    }


def _json_mapping(value: object, *, label: str) -> dict:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError as exc:
        raise CurriculumValidationError(f"installed {label} JSON is invalid") from exc
    if not isinstance(parsed, Mapping):
        raise CurriculumValidationError(f"installed {label} JSON is invalid")
    return dict(parsed)


def _verify_installed_content(conn: sqlite3.Connection, version: Mapping[str, object]) -> dict:
    version_id = int(version["id"])
    rows = conn.execute(
        "SELECT * FROM curriculum_nodes WHERE version_id=? ORDER BY upstream_id",
        (version_id,),
    ).fetchall()
    nodes_by_id = {int(row["id"]): row for row in rows}
    books_by_upstream = {
        str(row["upstream_id"]): row for row in rows if str(row["node_type"]) == "Book"
    }
    raw_nodes = []
    expected_aliases = set()
    for row in rows:
        upstream_id = str(row["upstream_id"])
        node_type = str(row["node_type"])
        properties = _json_mapping(row["source_properties_json"], label="node properties")
        aliases = properties.get("aliases") if isinstance(properties.get("aliases"), list) else []
        aliases = [str(alias).strip() for alias in aliases if str(alias).strip()]
        book_upstream_id = _book_upstream_id(upstream_id)
        book = books_by_upstream.get(book_upstream_id)
        if not book:
            raise CurriculumValidationError("installed curriculum book scope is missing")
        stage_key, grade_key, semester_key = _book_scope(
            {"id": book["upstream_id"], "name": book["canonical_name"]}
        )
        expected_columns = {
            "node_key": f"k12kg.{upstream_id}",
            "node_type": node_type,
            "knowledge_point_kind": node_type if node_type in KNOWLEDGE_POINT_TYPES else None,
            "subject_key": "math",
            "book_upstream_id": book_upstream_id,
            "aliases_json": canonical_json(aliases),
            "description": str(properties.get("definition") or properties.get("description") or "").strip(),
            "importance": str(properties.get("importance") or "").strip(),
            "source_locator": str(properties.get("pages") or "").strip(),
            "stage_key": stage_key,
            "grade_key": grade_key,
            "semester_key": semester_key,
        }
        for column, expected in expected_columns.items():
            if row[column] != expected:
                raise CurriculumValidationError(f"installed curriculum node derivation mismatch: {column}")
        if node_type in KNOWLEDGE_POINT_TYPES:
            seen = set()
            for alias in [str(row["canonical_name"]), *aliases]:
                normalized = normalize_alias(alias)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                expected_aliases.add(
                    (
                        int(row["id"]),
                        alias,
                        normalized,
                        "canonical" if alias == str(row["canonical_name"]) else "upstream",
                    )
                )
        raw_node = {
            "id": upstream_id,
            "label": node_type,
            "name": str(row["canonical_name"]),
        }
        # The pinned upstream omits the properties key for property-less
        # nodes. Preserve that distinction when rebuilding its canonical hash.
        if properties:
            raw_node["properties"] = properties
        raw_nodes.append(raw_node)
    actual_aliases = {
        (int(row["node_id"]), str(row["alias"]), str(row["normalized_alias"]), str(row["source"]))
        for row in conn.execute(
            """
            SELECT node_id, alias, normalized_alias, source
            FROM curriculum_node_aliases WHERE version_id=?
            """,
            (version_id,),
        ).fetchall()
    }
    if actual_aliases != expected_aliases:
        raise CurriculumValidationError("installed curriculum aliases mismatch")
    actual_legacy_targets = {
        str(row["legacy_knowledge_point_key"]): str(row["upstream_id"])
        for row in conn.execute(
            """
            SELECT legacy.legacy_knowledge_point_key, node.upstream_id
            FROM curriculum_legacy_knowledge_point_map legacy
            JOIN curriculum_nodes node ON node.id=legacy.curriculum_node_id
            WHERE legacy.version_id=?
            """,
            (version_id,),
        ).fetchall()
    }
    if actual_legacy_targets != LEGACY_KNOWLEDGE_POINT_TARGETS:
        raise CurriculumValidationError("installed curriculum legacy mapping mismatch")

    edge_rows = conn.execute(
        """
        SELECT edge.*, source.upstream_id AS source_upstream_id,
               target.upstream_id AS target_upstream_id
        FROM curriculum_edges edge
        JOIN curriculum_nodes source ON source.id=edge.source_node_id
        JOIN curriculum_nodes target ON target.id=edge.target_node_id
        WHERE edge.version_id=?
        ORDER BY edge.relation_type, source.upstream_id, target.upstream_id
        """,
        (version_id,),
    ).fetchall()
    raw_edges = [
        {
            "source": str(row["source_upstream_id"]),
            "target": str(row["target_upstream_id"]),
            "type": str(row["relation_type"]),
            "properties": _json_mapping(row["source_properties_json"], label="edge properties"),
        }
        for row in edge_rows
    ]
    installed_content_hash = content_hash({"nodes": raw_nodes, "edges": raw_edges})
    if installed_content_hash != str(version["content_hash"]):
        raise CurriculumValidationError("installed curriculum content hash mismatch")

    children_by_parent: dict[int, set[int]] = defaultdict(set)
    appears_in = []
    for row in edge_rows:
        relation = str(row["relation_type"])
        source_id = int(row["source_node_id"])
        target_id = int(row["target_node_id"])
        if relation == "is_part_of" and str(nodes_by_id[source_id]["node_type"]) in {"Chapter", "Section"}:
            children_by_parent[target_id].add(source_id)
        elif relation == "appears_in" and str(nodes_by_id[source_id]["node_type"]) in KNOWLEDGE_POINT_TYPES:
            appears_in.append((source_id, target_id))
    expected_membership = set()
    for book in books_by_upstream.values():
        book_id = int(book["id"])
        structural = {book_id}
        queue = deque([book_id])
        while queue:
            parent_id = queue.popleft()
            for child_id in children_by_parent.get(parent_id, set()):
                if child_id not in structural:
                    structural.add(child_id)
                    queue.append(child_id)
        expected_membership.update((book_id, node_id, "structural") for node_id in structural)
        expected_membership.update(
            (book_id, source_id, "appears_in")
            for source_id, target_id in appears_in
            if target_id in structural
        )
    actual_membership = {
        (int(row["book_node_id"]), int(row["node_id"]), str(row["membership_type"]))
        for row in conn.execute(
            """
            SELECT book_node_id, node_id, membership_type
            FROM curriculum_book_nodes WHERE version_id=?
            """,
            (version_id,),
        ).fetchall()
    }
    if actual_membership != expected_membership:
        raise CurriculumValidationError("installed curriculum book membership mismatch")
    return {
        "content_hash": installed_content_hash,
        "alias_count": len(actual_aliases),
        "book_membership_count": len(actual_membership),
    }


def verify_installed_curriculum(conn: sqlite3.Connection, version_id: int) -> dict:
    version = get_curriculum_version(conn, version_id)
    if not version:
        raise LookupError("curriculum version not found")
    node_counts = {
        row["node_type"]: int(row["count"])
        for row in conn.execute(
            "SELECT node_type, COUNT(*) AS count FROM curriculum_nodes WHERE version_id=? GROUP BY node_type",
            (int(version_id),),
        ).fetchall()
    }
    edge_counts = {
        row["relation_type"]: int(row["count"])
        for row in conn.execute(
            "SELECT relation_type, COUNT(*) AS count FROM curriculum_edges WHERE version_id=? GROUP BY relation_type",
            (int(version_id),),
        ).fetchall()
    }
    if node_counts != EXPECTED_IMPORT_NODE_COUNTS or edge_counts != EXPECTED_IMPORT_EDGE_COUNTS:
        raise CurriculumValidationError("installed curriculum counts mismatch")
    orphan_edges = int(conn.execute(
        """
        SELECT COUNT(*) FROM curriculum_edges edge
        LEFT JOIN curriculum_nodes source ON source.id=edge.source_node_id
        LEFT JOIN curriculum_nodes target ON target.id=edge.target_node_id
        WHERE edge.version_id=? AND (source.id IS NULL OR target.id IS NULL)
        """,
        (int(version_id),),
    ).fetchone()[0])
    if orphan_edges:
        raise CurriculumValidationError("installed curriculum has orphan edges")
    verified_content = _verify_installed_content(conn, version)
    return {
        "version": version,
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "node_total": sum(node_counts.values()),
        "edge_total": sum(edge_counts.values()),
        "knowledge_point_total": node_counts["Concept"] + node_counts["Skill"],
        "orphan_edges": orphan_edges,
        **verified_content,
    }
