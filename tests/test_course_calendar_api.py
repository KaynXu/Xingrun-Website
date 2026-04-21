import gc
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


class CourseCalendarApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        self.owner_token = owner_payload["token"]

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def approve_user(self, username: str, display_name: str) -> dict:
        submit = self.client.post(
            "/api/register-request",
            json={
                "username": username,
                "display_name": display_name,
                "password": "memberpass123",
                "organization_name": "星润Starain",
                "recovery_phone": "13800000000",
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(pending.status_code, 200)
        request_id = next(
            item["id"]
            for item in pending.get_json()["items"]
            if item["username"] == username
        )
        approve = self.client.post(
            f"/api/admin/registration-requests/{request_id}/approve",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(approve.status_code, 200)

        login = self.client.post(
            "/api/login",
            json={"username": username, "password": "memberpass123"},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        return payload

    def test_course_calendar_schedules_are_independent_from_review_plan_lessons(self):
        class_id = lesson_manager.save_class("六年级数学排课班", subject="数学", grade="六年级")
        lesson_manager.save_lesson(
            "2026-04-20",
            "数学",
            "六年级",
            "复习计划测试课",
            "summary",
            "",
            {"questions": []},
            "",
            class_id,
        )

        empty_calendar = self.client.get(
            "/api/course-calendar/schedules?start_date=2026-04-20&end_date=2026-04-26",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(empty_calendar.status_code, 200)
        empty_payload = empty_calendar.get_json()
        self.assertIsNotNone(empty_payload)
        self.assertEqual(empty_payload["items"], [])

        created = self.client.post(
            "/api/course-calendar/schedules",
            headers=self.auth_headers(self.owner_token),
            json={
                "class_id": class_id,
                "date": "2026-04-20",
                "time_block": "14:00-16:00",
                "start_offset_minutes": 15,
            },
        )
        self.assertEqual(created.status_code, 201)
        created_payload = created.get_json()
        self.assertIsNotNone(created_payload)
        self.assertEqual(created_payload["item"]["class_id"], class_id)
        self.assertEqual(created_payload["item"]["time_block"], "14:00-16:00")
        self.assertEqual(created_payload["item"]["start_offset_minutes"], 15)

        listed = self.client.get(
            "/api/course-calendar/schedules?start_date=2026-04-20&end_date=2026-04-26",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(listed.status_code, 200)
        listed_payload = listed.get_json()
        self.assertIsNotNone(listed_payload)
        self.assertEqual([item["id"] for item in listed_payload["items"]], [created_payload["item"]["id"]])

    def test_member_only_sees_and_schedules_assigned_classes(self):
        target_member = self.approve_user("calendar_member", "Calendar Member")
        other_member = self.approve_user("calendar_other", "Calendar Other")
        target_member_id = target_member["user"]["id"]
        other_member_id = other_member["user"]["id"]

        owned_class_id = lesson_manager.save_class("负责班级", subject="数学", grade="六年级")
        other_class_id = lesson_manager.save_class("其他班级", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(owned_class_id, target_member_id)
        lesson_manager.set_class_teacher_user_id(other_class_id, other_member_id)

        owner_schedule = self.client.post(
            "/api/course-calendar/schedules",
            headers=self.auth_headers(self.owner_token),
            json={"class_id": owned_class_id, "date": "2026-04-21", "time_block": "08:00-10:00"},
        )
        self.assertEqual(owner_schedule.status_code, 201)
        other_schedule = self.client.post(
            "/api/course-calendar/schedules",
            headers=self.auth_headers(self.owner_token),
            json={"class_id": other_class_id, "date": "2026-04-21", "time_block": "10:00-12:00"},
        )
        self.assertEqual(other_schedule.status_code, 201)

        listed = self.client.get(
            "/api/course-calendar/schedules?start_date=2026-04-20&end_date=2026-04-26",
            headers=self.auth_headers(target_member["token"]),
        )
        self.assertEqual(listed.status_code, 200)
        listed_payload = listed.get_json()
        self.assertIsNotNone(listed_payload)
        self.assertEqual([item["class_id"] for item in listed_payload["items"]], [owned_class_id])

        forbidden = self.client.post(
            "/api/course-calendar/schedules",
            headers=self.auth_headers(target_member["token"]),
            json={"class_id": other_class_id, "date": "2026-04-22", "time_block": "14:00-16:00"},
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_course_calendar_rejects_out_of_range_start_offset(self):
        class_id = lesson_manager.save_class("微调测试班", subject="数学", grade="六年级")

        invalid = self.client.post(
            "/api/course-calendar/schedules",
            headers=self.auth_headers(self.owner_token),
            json={
                "class_id": class_id,
                "date": "2026-04-20",
                "time_block": "08:00-10:00",
                "start_offset_minutes": 240,
            },
        )

        self.assertEqual(invalid.status_code, 400)

    def test_course_calendar_migrates_legacy_afternoon_slots(self):
        class_id = lesson_manager.save_class("旧时间段排课班", subject="数学", grade="六年级")
        with lesson_manager.get_conn() as conn:
            class_row = conn.execute("SELECT organization_id FROM classes WHERE id=?", (class_id,)).fetchone()
            self.assertIsNotNone(class_row)
            conn.execute(
                """
                INSERT INTO course_calendar_schedules
                    (organization_id, class_id, date, time_block, created_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (class_row["organization_id"], class_id, "2026-04-20", "13:00-15:00", None),
            )

        lesson_manager.init_db()

        listed = self.client.get(
            "/api/course-calendar/schedules?start_date=2026-04-20&end_date=2026-04-26",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(listed.status_code, 200)
        listed_payload = listed.get_json()
        self.assertIsNotNone(listed_payload)
        self.assertEqual([item["time_block"] for item in listed_payload["items"]], ["14:00-16:00"])


if __name__ == "__main__":
    unittest.main()
