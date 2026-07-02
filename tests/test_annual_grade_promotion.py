import gc
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
from app import app


class AnnualGradePromotionTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        self.owner_token = login.get_json()["token"]

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def test_annual_promotion_updates_active_classes_and_is_idempotent_by_academic_year(self):
        fifth_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="五年级",
            stage="小奥",
            current_grade="五年级",
            class_number="1",
            cohort_year=2021,
            show_cohort_year=True,
        )
        sixth_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="六年级",
            stage="小奥",
            current_grade="六年级",
            class_number="2",
            cohort_year=2020,
            show_cohort_year=True,
        )
        bridge_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="六年级",
            stage="小奥",
            current_grade="六年级",
            class_number="3",
            cohort_year=2020,
            show_cohort_year=True,
            is_bridge=True,
            bridge_target="小学衔接初中",
        )
        high_three_id = lesson_manager.save_class(
            "",
            subject="物理",
            grade="高三",
            stage="高中",
            current_grade="高三",
            class_number="1",
            cohort_year=2023,
            show_cohort_year=True,
        )
        unknown_id = lesson_manager.save_class("老师小课", subject="数学")

        result = lesson_manager.promote_classes_for_academic_year(today="2026-06-30")

        self.assertIn(fifth_id, result["promoted_ids"])
        self.assertIn(bridge_id, result["promoted_ids"])
        self.assertIn(sixth_id, result["pending_ids"])
        self.assertIn(high_three_id, result["pending_ids"])
        self.assertIn(unknown_id, result["skipped_ids"])

        fifth = lesson_manager.get_class(fifth_id)
        self.assertEqual(fifth["current_grade"], "六年级")
        self.assertEqual(fifth["lifecycle_status"], "active")
        self.assertEqual(fifth["last_promoted_at"], "2026-06-30")

        bridge = lesson_manager.get_class(bridge_id)
        self.assertEqual(bridge["current_grade"], "七年级")
        self.assertEqual(bridge["stage"], "初中")
        self.assertEqual(bridge["cohort_year"], 2026)
        self.assertFalse(bridge["is_bridge"])
        self.assertEqual(bridge["bridge_target"], "")
        self.assertEqual(bridge["name"], "数学·初2026级·七年级·3班")

        sixth = lesson_manager.get_class(sixth_id)
        self.assertEqual(sixth["current_grade"], "六年级")
        self.assertEqual(sixth["lifecycle_status"], "pending_graduation")
        self.assertEqual(sixth["graduation_academic_year_start"], 2026)
        self.assertEqual(sixth["last_promoted_at"], "2026-06-30")

        high_three = lesson_manager.get_class(high_three_id)
        self.assertEqual(high_three["current_grade"], "高三")
        self.assertEqual(high_three["lifecycle_status"], "pending_graduation")

        unknown = lesson_manager.get_class(unknown_id)
        self.assertEqual(unknown["current_grade"], "")
        self.assertEqual(unknown["lifecycle_status"], "active")
        self.assertEqual(unknown["last_promoted_at"], "")

        with lesson_manager.get_conn() as conn:
            run = conn.execute(
                """
                SELECT status, summary_json
                FROM academic_year_promotion_runs
                WHERE organization_id=1 AND academic_year_start=2026
                """
            ).fetchone()
        self.assertEqual(run["status"], "completed_with_skips")
        self.assertEqual(json.loads(run["summary_json"]), {
            "promoted": 2,
            "pending_graduation": 2,
            "skipped_unknown_grade": 1,
            "effective_date": "2026-06-30",
        })

        second_result = lesson_manager.promote_classes_for_academic_year(today="2026-07-02")
        self.assertEqual(second_result["promoted_ids"], [])
        self.assertEqual(second_result["pending_ids"], [])
        self.assertEqual(second_result["skipped_ids"], [])
        self.assertEqual(second_result["already_executed_org_ids"], [1])
        self.assertEqual(lesson_manager.get_class(fifth_id)["current_grade"], "六年级")

    def test_classes_api_defaults_to_current_scope_and_all_scope_includes_pending_graduation(self):
        active_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="五年级",
            stage="小奥",
            current_grade="五年级",
            class_number="1",
        )
        pending_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="九年级",
            stage="初中",
            current_grade="九年级",
            class_number="2",
        )
        lesson_manager.promote_classes_for_academic_year(today="2026-06-30")

        current_response = self.client.get("/api/classes", headers=self.auth_headers(self.owner_token))
        self.assertEqual(current_response.status_code, 200)
        current_ids = [item["id"] for item in current_response.get_json()]
        self.assertIn(active_id, current_ids)
        self.assertNotIn(pending_id, current_ids)

        all_response = self.client.get("/api/classes?scope=all", headers=self.auth_headers(self.owner_token))
        self.assertEqual(all_response.status_code, 200)
        all_items = all_response.get_json()
        all_by_id = {item["id"]: item for item in all_items}
        self.assertIn(pending_id, all_by_id)
        self.assertEqual(all_by_id[pending_id]["lifecycle_status"], "pending_graduation")

    def test_course_calendar_hides_and_rejects_pending_graduation_classes(self):
        pending_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="九年级",
            stage="初中",
            current_grade="九年级",
            class_number="1",
        )
        create_before = self.client.post(
            "/api/course-calendar/schedules",
            headers=self.auth_headers(self.owner_token),
            json={"class_id": pending_id, "date": "2026-07-03", "time_block": "08:00-10:00"},
        )
        self.assertEqual(create_before.status_code, 201)

        lesson_manager.promote_classes_for_academic_year(today="2026-06-30")

        listed = self.client.get(
            "/api/course-calendar/schedules?start_date=2026-07-01&end_date=2026-07-10",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["items"], [])

        create_after = self.client.post(
            "/api/course-calendar/schedules",
            headers=self.auth_headers(self.owner_token),
            json={"class_id": pending_id, "date": "2026-07-04", "time_block": "10:00-12:00"},
        )
        self.assertEqual(create_after.status_code, 400)
        self.assertEqual(create_after.get_json()["error"], "class is not active")

    def test_review_plan_list_hides_pending_graduation_class_lessons_by_default(self):
        active_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="五年级",
            stage="小奥",
            current_grade="五年级",
            class_number="1",
        )
        pending_id = lesson_manager.save_class(
            "",
            subject="数学",
            grade="九年级",
            stage="初中",
            current_grade="九年级",
            class_number="2",
        )
        active_lesson_id = lesson_manager.save_lesson(
            "2026-07-02",
            "数学",
            "五年级",
            "当前班级课程",
            "",
            "",
            {},
            "",
            class_id=active_id,
        )
        pending_lesson_id = lesson_manager.save_lesson(
            "2026-07-02",
            "数学",
            "九年级",
            "待结业班级课程",
            "",
            "",
            {},
            "",
            class_id=pending_id,
        )
        lesson_manager.promote_classes_for_academic_year(today="2026-06-30")

        current_response = self.client.get("/api/review-plans", headers=self.auth_headers(self.owner_token))
        self.assertEqual(current_response.status_code, 200)
        current_ids = [item["id"] for item in current_response.get_json()]
        self.assertIn(active_lesson_id, current_ids)
        self.assertNotIn(pending_lesson_id, current_ids)

        all_response = self.client.get("/api/review-plans?scope=all", headers=self.auth_headers(self.owner_token))
        self.assertEqual(all_response.status_code, 200)
        all_ids = [item["id"] for item in all_response.get_json()]
        self.assertIn(active_lesson_id, all_ids)
        self.assertIn(pending_lesson_id, all_ids)


if __name__ == "__main__":
    unittest.main()
