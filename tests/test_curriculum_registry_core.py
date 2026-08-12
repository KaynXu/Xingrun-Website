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
                subject_key TEXT NOT NULL,
                grade TEXT DEFAULT '',
                current_grade TEXT DEFAULT ''
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

    def test_auto_scope_matches_both_books_and_supports_manual_multibook_override(self):
        version_id = self._activate()
        self.conn.execute(
            "UPDATE classes SET current_grade='九年级', grade='九年级' WHERE id=21"
        )
        automatic = curriculum_registry.get_effective_class_curriculum_scope(
            self.conn, 21
        )
        self.assertEqual(automatic["assignment_mode"], "auto")
        self.assertEqual(
            [item["book_upstream_id"] for item in automatic["books"]],
            ["math_9a_rjb", "math_9b_rjb"],
        )
        registry = curriculum_registry.get_extraction_registry(
            self.conn,
            organization_id=1,
            class_id=21,
            subject_key="math",
        )
        self.assertEqual(registry["registry_metadata"]["count"], 172)
        self.assertEqual(len(registry["registry"]), 172)

        manual = curriculum_registry.replace_class_curriculum_books(
            self.conn,
            organization_id=1,
            class_id=21,
            version_id=version_id,
            book_node_ids=[item["book_node_id"] for item in reversed(automatic["books"])],
            primary_book_node_id=automatic["books"][0]["book_node_id"],
            actor_user_id=11,
            request_id="manual-both-books",
            expected_cas_token=automatic["cas_token"],
        )
        self.assertEqual(manual["assignment_mode"], "manual")
        self.assertEqual(len(manual["books"]), 2)
        replay = curriculum_registry.replace_class_curriculum_books(
            self.conn,
            organization_id=1,
            class_id=21,
            version_id=version_id,
            book_node_ids=[item["book_node_id"] for item in automatic["books"]],
            primary_book_node_id=automatic["books"][0]["book_node_id"],
            actor_user_id=11,
            request_id="manual-both-books",
            expected_cas_token=automatic["cas_token"],
        )
        self.assertEqual(replay["scope_hash"], manual["scope_hash"])
        active_count = self.conn.execute(
            "SELECT COUNT(*) FROM curriculum_class_assignments WHERE class_id=21 AND status='active'"
        ).fetchone()[0]
        self.assertEqual(active_count, 2)

    def test_legacy_single_book_receipt_replays_after_multibook_upgrade(self):
        version_id = self._activate()
        book = self.conn.execute(
            "SELECT id FROM curriculum_nodes WHERE version_id=? AND upstream_id='math_9a_rjb'",
            (version_id,),
        ).fetchone()
        first = curriculum_registry.assign_curriculum_book(
            self.conn,
            organization_id=1,
            class_id=21,
            version_id=version_id,
            book_node_id=int(book["id"]),
            actor_user_id=11,
            request_id="legacy-single-replay",
            expected_assignment_id=None,
        )
        legacy_result = curriculum_registry.serialize_class_assignment(
            self.conn, int(first["id"])
        )
        self.conn.execute(
            "UPDATE curriculum_assignment_requests SET result_json=? WHERE organization_id=1 AND request_id=?",
            (
                curriculum_registry.canonical_json(legacy_result),
                "legacy-single-replay",
            ),
        )
        replay = curriculum_registry.assign_curriculum_book(
            self.conn,
            organization_id=1,
            class_id=21,
            version_id=version_id,
            book_node_id=int(book["id"]),
            actor_user_id=11,
            request_id="legacy-single-replay",
            expected_assignment_id=None,
        )
        self.assertEqual(int(replay["id"]), int(first["id"]))
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM curriculum_class_assignments WHERE class_id=21"
            ).fetchone()[0],
            1,
        )

    def test_assignment_cas_serializes_two_connections_and_rejects_stale_token(self):
        version_id = self._activate()
        self.conn.execute(
            "UPDATE classes SET current_grade='九年级', grade='九年级' WHERE id=21"
        )
        initial = curriculum_registry.get_effective_class_curriculum_scope(self.conn, 21)
        self.conn.commit()
        first_conn = sqlite3.connect(self.db_path, timeout=2)
        second_conn = sqlite3.connect(self.db_path, timeout=0.05)
        first_conn.row_factory = sqlite3.Row
        second_conn.row_factory = sqlite3.Row
        try:
            first = curriculum_registry.replace_class_curriculum_books(
                first_conn,
                organization_id=1,
                class_id=21,
                version_id=version_id,
                book_node_ids=[initial["books"][0]["book_node_id"]],
                primary_book_node_id=initial["books"][0]["book_node_id"],
                actor_user_id=11,
                request_id="cas-first",
                expected_cas_token=initial["cas_token"],
            )
            with self.assertRaisesRegex(sqlite3.OperationalError, "database is locked"):
                curriculum_registry.replace_class_curriculum_books(
                    second_conn,
                    organization_id=1,
                    class_id=21,
                    version_id=version_id,
                    book_node_ids=[initial["books"][1]["book_node_id"]],
                    primary_book_node_id=initial["books"][1]["book_node_id"],
                    actor_user_id=11,
                    request_id="cas-second",
                    expected_cas_token=initial["cas_token"],
                )
            second_conn.rollback()
            first_conn.commit()
            with self.assertRaisesRegex(
                curriculum_registry.CurriculumConflictError,
                "assignment changed",
            ):
                curriculum_registry.replace_class_curriculum_books(
                    second_conn,
                    organization_id=1,
                    class_id=21,
                    version_id=version_id,
                    book_node_ids=[initial["books"][1]["book_node_id"]],
                    primary_book_node_id=initial["books"][1]["book_node_id"],
                    actor_user_id=11,
                    request_id="cas-second",
                    expected_cas_token=initial["cas_token"],
                )
            second_conn.rollback()
            current = curriculum_registry.get_effective_class_curriculum_scope(
                first_conn, 21
            )
            self.assertEqual(current["scope_hash"], first["scope_hash"])
            self.assertEqual(current["book_node_ids"], [initial["books"][0]["book_node_id"]])
        finally:
            first_conn.close()
            second_conn.close()

    def test_assignment_validation_and_deprecated_manual_scope_require_review(self):
        version_id = self._activate()
        self.conn.execute(
            "UPDATE classes SET current_grade='九年级', grade='九年级' WHERE id=21"
        )
        automatic = curriculum_registry.get_effective_class_curriculum_scope(self.conn, 21)
        with self.assertRaisesRegex(
            curriculum_registry.CurriculumValidationError,
            "positive integers",
        ):
            curriculum_registry.replace_class_curriculum_books(
                self.conn,
                organization_id=1,
                class_id=21,
                version_id=version_id,
                book_node_ids=[automatic["books"][0]["book_node_id"], None],
                primary_book_node_id=automatic["books"][0]["book_node_id"],
                actor_user_id=11,
                request_id="malformed-books",
                expected_cas_token=automatic["cas_token"],
            )
        manual = curriculum_registry.replace_class_curriculum_books(
            self.conn,
            organization_id=1,
            class_id=21,
            version_id=version_id,
            book_node_ids=[automatic["books"][0]["book_node_id"]],
            primary_book_node_id=automatic["books"][0]["book_node_id"],
            actor_user_id=11,
            request_id="manual-before-deprecation",
            expected_cas_token=automatic["cas_token"],
        )
        self.assertEqual(manual["assignment_mode"], "manual")
        self.conn.execute(
            "UPDATE curriculum_versions SET status='deprecated' WHERE id=?",
            (version_id,),
        )
        review = curriculum_registry.get_effective_class_curriculum_scope(self.conn, 21)
        self.assertEqual(review["assignment_mode"], "needs_review")
        self.assertEqual(review["version_status"], "deprecated")
        self.assertEqual(len(review["books"]), 1)
        self.assertIn("已停用", review["needs_review_reason"])

    def test_grade_seven_union_exceeds_legacy_limit_without_truncation(self):
        self._activate()
        self.conn.execute(
            "UPDATE classes SET current_grade='七年级', grade='七年级' WHERE id=21"
        )
        registry = curriculum_registry.get_extraction_registry(
            self.conn,
            organization_id=1,
            class_id=21,
            subject_key="math",
        )
        self.assertEqual(registry["registry_metadata"]["count"], 235)
        self.assertEqual(len(registry["registry"]), 235)
        self.assertFalse(registry["registry_metadata"]["truncated"])

    def test_grades_one_through_nine_infer_both_semester_books(self):
        self._activate()
        chinese_grades = "一二三四五六七八九"
        expected_counts = [173, 135, 141, 148, 124, 106, 235, 202, 172]
        for grade_number, (grade_name, expected_count) in enumerate(
            zip(chinese_grades, expected_counts),
            start=1,
        ):
            with self.subTest(grade=grade_number):
                self.conn.execute(
                    "UPDATE classes SET current_grade=?, grade=? WHERE id=21",
                    (f"{grade_name}年级", f"{grade_name}年级"),
                )
                scope = curriculum_registry.get_effective_class_curriculum_scope(
                    self.conn, 21
                )
                self.assertEqual(scope["assignment_mode"], "auto")
                self.assertEqual(
                    [item["book_upstream_id"] for item in scope["books"]],
                    [f"math_{grade_number}a_rjb", f"math_{grade_number}b_rjb"],
                )
                registry = curriculum_registry.get_extraction_registry(
                    self.conn,
                    organization_id=1,
                    class_id=21,
                    subject_key="math",
                )
                self.assertEqual(registry["registry_metadata"]["count"], expected_count)

    def test_high_school_and_unknown_grade_require_review(self):
        self._activate()
        for grade in ("高一", "国际课程"):
            with self.subTest(grade=grade):
                self.conn.execute(
                    "UPDATE classes SET current_grade=?, grade=? WHERE id=21",
                    (grade, grade),
                )
                scope = curriculum_registry.get_effective_class_curriculum_scope(
                    self.conn, 21
                )
                self.assertEqual(scope["assignment_mode"], "needs_review")
                self.assertEqual(scope["books"], [])
                self.assertTrue(scope["needs_review_reason"])

    def test_unambiguous_class_name_is_safe_fallback_when_grade_columns_are_empty(self):
        self._activate()
        self.conn.execute(
            "UPDATE classes SET name='数学·九年级·7班', current_grade='', grade='' WHERE id=21"
        )
        scope = curriculum_registry.get_effective_class_curriculum_scope(self.conn, 21)
        self.assertEqual(scope["assignment_mode"], "auto")
        self.assertEqual(scope["inferred_grade_key"], "grade_9")
        self.assertEqual(scope["inference_source"], "classes.name")
        self.assertEqual(
            [item["book_upstream_id"] for item in scope["books"]],
            ["math_9a_rjb", "math_9b_rjb"],
        )

        self.conn.execute(
            "UPDATE classes SET name='六年级至七年级衔接班' WHERE id=21"
        )
        ambiguous = curriculum_registry.get_effective_class_curriculum_scope(self.conn, 21)
        self.assertEqual(ambiguous["assignment_mode"], "needs_review")
        self.assertEqual(ambiguous["books"], [])

    def test_cross_book_alias_ambiguity_fails_closed_but_exact_key_resolves(self):
        self._activate()
        self.conn.execute(
            "UPDATE classes SET current_grade='一年级', grade='一年级' WHERE id=21"
        )
        registry = curriculum_registry.get_extraction_registry(
            self.conn,
            organization_id=1,
            class_id=21,
            subject_key="math",
        )["registry"]
        matches = [
            item
            for item in registry
            if curriculum_registry.normalize_alias(item["canonical_name"])
            == curriculum_registry.normalize_alias("比较数量")
        ]
        self.assertEqual(len(matches), 2)
        self.assertIsNone(
            curriculum_registry.resolve_curriculum_knowledge_point(
                self.conn,
                organization_id=1,
                class_id=21,
                subject_key="math",
                value="比较数量",
            )
        )
        for match in matches:
            resolved = curriculum_registry.resolve_curriculum_knowledge_point(
                self.conn,
                organization_id=1,
                class_id=21,
                subject_key="math",
                value=match["knowledge_point_key"],
            )
            self.assertEqual(resolved["knowledge_point_key"], match["knowledge_point_key"])

    def test_existing_single_assignment_schema_upgrades_without_data_loss(self):
        version_id = self._activate()
        book = self.conn.execute(
            "SELECT id FROM curriculum_nodes WHERE version_id=? AND upstream_id='math_9a_rjb'",
            (version_id,),
        ).fetchone()
        assignment = curriculum_registry.assign_curriculum_book(
            self.conn,
            organization_id=1,
            class_id=21,
            version_id=version_id,
            book_node_id=int(book["id"]),
            actor_user_id=11,
            request_id="old-single-book",
            expected_assignment_id=None,
        )
        self.conn.execute("DROP INDEX idx_curriculum_class_assignment_active_book")
        self.conn.execute("ALTER TABLE curriculum_class_assignments DROP COLUMN is_primary")
        self.conn.execute(
            "CREATE UNIQUE INDEX idx_curriculum_class_assignment_active "
            "ON curriculum_class_assignments(class_id) WHERE status='active'"
        )
        curriculum_registry.ensure_curriculum_schema(self.conn)
        indexes = {
            row["name"]
            for row in self.conn.execute("PRAGMA index_list(curriculum_class_assignments)")
        }
        upgraded = self.conn.execute(
            "SELECT * FROM curriculum_class_assignments WHERE id=?",
            (int(assignment["id"]),),
        ).fetchone()
        columns = {
            str(row["name"])
            for row in self.conn.execute("PRAGMA table_info(curriculum_class_assignments)")
        }
        self.assertNotIn("idx_curriculum_class_assignment_active", indexes)
        self.assertIn("idx_curriculum_class_assignment_active_book", indexes)
        self.assertIn("is_primary", columns)
        self.assertEqual(upgraded["status"], "active")
        self.assertEqual(int(upgraded["book_node_id"]), int(book["id"]))
        self.assertEqual(self.conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

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
