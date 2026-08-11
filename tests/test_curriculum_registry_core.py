import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import curriculum_registry
from class_commentary_semantica import SemanticaGraphAdapter


class CurriculumRegistryCoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "curriculum.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(
            """
            CREATE TABLE organizations (id INTEGER PRIMARY KEY);
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            CREATE TABLE classes (
                id INTEGER PRIMARY KEY,
                organization_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                subject_key TEXT NOT NULL
            );
            INSERT INTO organizations(id) VALUES (1);
            INSERT INTO users(id) VALUES (11);
            INSERT INTO classes(id, organization_id, name, subject_key)
            VALUES (21, 1, 'Curriculum Core', 'math');
            """
        )
        curriculum_registry.ensure_curriculum_schema(self.conn)
        self.bundle = curriculum_registry.load_bundle()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _import(self):
        return curriculum_registry.import_curriculum_bundle(
            self.conn, self.bundle, actor_user_id=11
        )

    def _activate(self):
        imported = self._import()
        version_id = int(imported["version"]["id"])
        curriculum_registry.review_curriculum_version(
            self.conn, version_id, actor_user_id=11
        )
        curriculum_registry.activate_curriculum_version(
            self.conn, version_id, actor_user_id=11
        )
        return version_id

    def test_real_pinned_bundle_receipt_full_import_replay_and_membership(self):
        raw = curriculum_registry.DEFAULT_BUNDLE_PATH.read_bytes()
        receipt = json.loads(
            curriculum_registry.DEFAULT_RECEIPT_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "2d6562f8c8efa490a0a4ccbd38def8eaeca43816c4aec91f2da1d52756bee7f5",
        )
        self.assertEqual(receipt["source_sha256"], curriculum_registry.SOURCE_SHA256)
        self.assertEqual(receipt["data_license"], "CC BY-NC-SA 4.0")
        self.assertEqual(receipt["code_license"], "MIT")
        self.assertEqual(receipt["source_counts"]["nodes"]["Exercise"], 474)
        self.assertEqual(receipt["import_counts"]["nodes"]["Concept"], 1470)
        stats = curriculum_registry.validate_bundle(self.bundle)
        self.assertEqual(
            stats,
            {
                "node_counts": curriculum_registry.EXPECTED_IMPORT_NODE_COUNTS,
                "edge_counts": curriculum_registry.EXPECTED_IMPORT_EDGE_COUNTS,
                "node_total": 2237,
                "edge_total": 4007,
                "knowledge_point_total": 1898,
                "content_hash": "9187765c1eb1b5f1b55c5f751b50dd7e5f203c7327f99983e7a957bf87dc326b",
            },
        )
        first = self._import()
        replay = self._import()
        self.assertTrue(first["changed"])
        self.assertFalse(replay["changed"])
        verified = curriculum_registry.verify_installed_curriculum(
            self.conn, int(first["version"]["id"])
        )
        self.assertEqual(verified["node_total"], 2237)
        self.assertEqual(verified["edge_total"], 4007)
        self.assertEqual(verified["alias_count"], 2038)
        self.assertEqual(verified["book_membership_count"], 2386)
        books = curriculum_registry.list_curriculum_books(
            self.conn, int(first["version"]["id"])
        )
        self.assertEqual(len(books), 23)
        self.assertTrue(
            all(49 <= int(book["knowledge_point_count"]) <= 185 for book in books)
        )
        shared_membership = self.conn.execute(
            """
            SELECT COUNT(DISTINCT book.upstream_id)
            FROM curriculum_nodes node
            JOIN curriculum_book_nodes membership ON membership.node_id=node.id
            JOIN curriculum_nodes book ON book.id=membership.book_node_id
            WHERE node.node_key='k12kg.math_1a_rjb_cpt16'
              AND membership.membership_type='appears_in'
              AND book.upstream_id IN ('math_1a_rjb','math_bx2_rjb')
            """
        ).fetchone()[0]
        self.assertEqual(shared_membership, 2)
        legacy = {
            str(row["legacy_knowledge_point_key"]): str(row["upstream_id"])
            for row in self.conn.execute(
                """
                SELECT legacy.legacy_knowledge_point_key, node.upstream_id
                FROM curriculum_legacy_knowledge_point_map legacy
                JOIN curriculum_nodes node ON node.id=legacy.curriculum_node_id
                """
            )
        }
        self.assertEqual(legacy, curriculum_registry.LEGACY_KNOWLEDGE_POINT_TARGETS)

    def test_failure_rollback_hash_rejection_normalization_and_cycle_detection(self):
        with self.assertRaisesRegex(RuntimeError, "injected curriculum import failure"):
            curriculum_registry.import_curriculum_bundle(
                self.conn,
                self.bundle,
                actor_user_id=11,
                fail_after_nodes=25,
            )
        counts = tuple(
            self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "curriculum_packages",
                "curriculum_versions",
                "curriculum_nodes",
                "curriculum_edges",
            )
        )
        self.assertEqual(counts, (0, 0, 0, 0))
        self.assertEqual(
            curriculum_registry.normalize_alias("  ＡＢＣ\u3000  Estimation "),
            "abc estimation",
        )

        cycle = copy.deepcopy(self.bundle)
        prereqs = [
            (index, edge)
            for index, edge in enumerate(cycle["edges"])
            if edge["type"] == "prerequisites_for"
        ]
        existing = {
            (edge["source"], edge["target"], edge["type"])
            for edge in cycle["edges"]
        }
        first_edge = prereqs[0][1]
        replacement_index = next(
            index
            for index, edge in reversed(prereqs)
            if (first_edge["target"], first_edge["source"], "prerequisites_for")
            not in existing
            and edge is not first_edge
        )
        cycle["edges"][replacement_index] = {
            "source": first_edge["target"],
            "target": first_edge["source"],
            "type": "prerequisites_for",
            "properties": {},
        }
        with self.assertRaisesRegex(
            curriculum_registry.CurriculumValidationError,
            "prerequisite cycle detected",
        ):
            curriculum_registry.validate_bundle(cycle)

        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = Path(temp_dir) / "tampered.json"
            bundle_path.write_bytes(
                curriculum_registry.DEFAULT_BUNDLE_PATH.read_bytes() + b"\n"
            )
            with self.assertRaisesRegex(
                curriculum_registry.CurriculumValidationError,
                "bundle SHA-256 mismatch",
            ):
                curriculum_registry.load_bundle(
                    bundle_path, curriculum_registry.DEFAULT_RECEIPT_PATH
                )

    def test_ambiguous_alias_fails_closed_and_legacy_key_resolves_in_book_scope(self):
        version_id = self._activate()
        book = self.conn.execute(
            "SELECT id FROM curriculum_nodes WHERE version_id=? AND upstream_id='math_3a_rjb'",
            (version_id,),
        ).fetchone()
        assignment = curriculum_registry.assign_curriculum_book(
            self.conn,
            organization_id=1,
            class_id=21,
            version_id=version_id,
            book_node_id=int(book["id"]),
            actor_user_id=11,
            request_id="assign-3a",
            expected_assignment_id=None,
        )
        self.assertIsNone(
            curriculum_registry.resolve_curriculum_knowledge_point(
                self.conn,
                organization_id=1,
                class_id=21,
                subject_key="math",
                value="估算",
            )
        )
        self.conn.execute(
            "UPDATE curriculum_class_assignments SET status='removed', ended_at='now' WHERE id=?",
            (int(assignment["id"]),),
        )
        legacy_book = self.conn.execute(
            "SELECT id FROM curriculum_nodes WHERE version_id=? AND upstream_id='math_9a_rjb'",
            (version_id,),
        ).fetchone()
        curriculum_registry.assign_curriculum_book(
            self.conn,
            organization_id=1,
            class_id=21,
            version_id=version_id,
            book_node_id=int(legacy_book["id"]),
            actor_user_id=11,
            request_id="assign-9a",
            expected_assignment_id=None,
        )
        resolved = curriculum_registry.resolve_curriculum_knowledge_point(
            self.conn,
            organization_id=1,
            class_id=21,
            subject_key="math",
            value="math.quadratic_function_graph",
        )
        self.assertEqual(resolved["node_key"], "k12kg.math_9a_rjb_cpt17")

    def test_reviewed_content_and_provenance_are_immutable(self):
        imported = self._import()
        version_id = int(imported["version"]["id"])
        curriculum_registry.review_curriculum_version(
            self.conn, version_id, actor_user_id=11
        )
        node = self.conn.execute(
            "SELECT * FROM curriculum_nodes WHERE version_id=? LIMIT 1", (version_id,)
        ).fetchone()
        edge = self.conn.execute(
            "SELECT * FROM curriculum_edges WHERE version_id=? LIMIT 1", (version_id,)
        ).fetchone()
        membership = self.conn.execute(
            "SELECT * FROM curriculum_book_nodes WHERE version_id=? LIMIT 1",
            (version_id,),
        ).fetchone()
        statements = [
            ("UPDATE curriculum_nodes SET canonical_name='tampered' WHERE id=?", (node["id"],)),
            ("DELETE FROM curriculum_edges WHERE id=?", (edge["id"],)),
            (
                "DELETE FROM curriculum_book_nodes WHERE version_id=? AND book_node_id=? AND node_id=?",
                (version_id, membership["book_node_id"], membership["node_id"]),
            ),
            (
                "UPDATE curriculum_versions SET content_hash=? WHERE id=?",
                ("0" * 64, version_id),
            ),
            (
                "DELETE FROM curriculum_legacy_knowledge_point_map WHERE version_id=?",
                (version_id,),
            ),
        ]
        for sql, params in statements:
            with self.subTest(sql=sql):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.conn.execute(sql, params)
        verified = curriculum_registry.verify_installed_curriculum(self.conn, version_id)
        self.assertEqual(verified["content_hash"], imported["content_hash"])

    def test_complete_curriculum_snapshot_builds_all_semantica_nodes_and_edges(self):
        self._activate()
        snapshot = curriculum_registry.build_semantica_curriculum_snapshot(self.conn)
        self.assertEqual(snapshot["node_count"], 2237)
        self.assertEqual(snapshot["edge_count"], 4007)
        self.assertEqual(
            snapshot["content_hash"],
            curriculum_registry.content_hash(
                {"nodes": snapshot["nodes"], "edges": snapshot["edges"]}
            ),
        )
        nodes, edges = SemanticaGraphAdapter._curriculum_graph(snapshot)
        self.assertEqual((len(nodes), len(edges)), (2237, 4007))
        self.assertEqual(len({node["id"] for node in nodes}), 2237)
        self.assertEqual(len({edge["id"] for edge in edges}), 4007)
        self.assertEqual(
            {edge["type"] for edge in edges},
            {"IS_PART_OF", "APPEARS_IN", "IS_A", "PREREQUISITE_FOR", "RELATES_TO"},
        )


if __name__ == "__main__":
    unittest.main()
