import gc
import json
import tempfile
import unittest
from pathlib import Path

import config_runtime
import curriculum_registry
import lesson_manager


class ClassCurriculumAssignmentLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.old_db = lesson_manager.DB_PATH
        self.old_cfg = config_runtime.CFG_PATH
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner = lesson_manager.get_user_by_username("Kayn")
        with lesson_manager.get_conn() as conn:
            imported = curriculum_registry.import_curriculum_bundle(
                conn,
                curriculum_registry.load_bundle(),
                actor_user_id=int(self.owner["id"]),
            )
            self.version_id = int(imported["version"]["id"])
            curriculum_registry.review_curriculum_version(
                conn, self.version_id, actor_user_id=int(self.owner["id"])
            )
            curriculum_registry.activate_curriculum_version(
                conn, self.version_id, actor_user_id=int(self.owner["id"])
            )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        config_runtime.CFG_PATH = self.old_cfg
        gc.collect()
        self.temp_dir.cleanup()

    def _create_manual_class(self, grade: str, class_number: str) -> tuple[int, list[int]]:
        class_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade=grade,
            current_grade=grade,
            class_number=class_number,
        )
        with lesson_manager.get_conn() as conn:
            automatic = curriculum_registry.get_effective_class_curriculum_scope(
                conn, class_id
            )
            book_ids = [int(item["book_node_id"]) for item in automatic["books"]]
            curriculum_registry.replace_class_curriculum_books(
                conn,
                organization_id=int(self.owner["organization_id"]),
                class_id=class_id,
                version_id=self.version_id,
                book_node_ids=book_ids,
                primary_book_node_id=book_ids[0],
                actor_user_id=int(self.owner["id"]),
                request_id=f"manual-curriculum-{class_id}",
                expected_cas_token=str(automatic["cas_token"]),
            )
        return class_id, book_ids

    def _active_and_removed_counts(self, class_id: int) -> tuple[int, int]:
        with lesson_manager.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM curriculum_class_assignments
                WHERE class_id=? GROUP BY status
                """,
                (class_id,),
            ).fetchall()
        counts = {str(row["status"]): int(row["count"]) for row in rows}
        return counts.get("active", 0), counts.get("removed", 0)

    def test_update_class_removes_all_manual_books_on_grade_or_subject_change(self):
        grade_class_id, _ = self._create_manual_class("九年级", "7")
        subject_class_id, _ = self._create_manual_class("八年级", "3")

        lesson_manager.update_class(
            grade_class_id,
            "",
            subject="数学",
            grade="八年级",
            current_grade="八年级",
            class_number="7",
            actor_user_id=int(self.owner["id"]),
        )
        lesson_manager.update_class(
            subject_class_id,
            "",
            subject="物理",
            grade="八年级",
            current_grade="八年级",
            class_number="3",
            actor_user_id=int(self.owner["id"]),
        )

        self.assertEqual(self._active_and_removed_counts(grade_class_id), (0, 2))
        self.assertEqual(self._active_and_removed_counts(subject_class_id), (0, 2))
        with lesson_manager.get_conn() as conn:
            grade_scope = curriculum_registry.get_effective_class_curriculum_scope(
                conn, grade_class_id
            )
            subject_scope = curriculum_registry.get_effective_class_curriculum_scope(
                conn, subject_class_id
            )
            audits = conn.execute(
                """
                SELECT class_id, before_json, after_json
                FROM curriculum_audit_events
                WHERE action='remove_stale_class_assignments'
                  AND class_id IN (?, ?)
                ORDER BY class_id
                """,
                (grade_class_id, subject_class_id),
            ).fetchall()
        self.assertEqual(grade_scope["assignment_mode"], "auto")
        self.assertEqual(
            [item["book_upstream_id"] for item in grade_scope["books"]],
            ["math_8a_rjb", "math_8b_rjb"],
        )
        self.assertEqual(subject_scope["assignment_mode"], "needs_review")
        self.assertEqual(len(audits), 2)
        self.assertTrue(all(len(json.loads(row["before_json"])["assignments"]) == 2 for row in audits))

    def test_annual_promotion_removes_all_stale_manual_books(self):
        class_id, _ = self._create_manual_class("五年级", "9")

        result = lesson_manager.promote_classes_for_academic_year(today="2026-06-30")

        self.assertIn(class_id, result["promoted_ids"])
        self.assertEqual(self._active_and_removed_counts(class_id), (0, 2))
        with lesson_manager.get_conn() as conn:
            scope = curriculum_registry.get_effective_class_curriculum_scope(conn, class_id)
        self.assertEqual(scope["assignment_mode"], "auto")
        self.assertEqual(scope["inferred_grade_key"], "grade_6")
        self.assertEqual(
            [item["book_upstream_id"] for item in scope["books"]],
            ["math_6a_rjb", "math_6b_rjb"],
        )


if __name__ == "__main__":
    unittest.main()
