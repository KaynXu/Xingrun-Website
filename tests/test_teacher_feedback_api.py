import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import credit_manager
import lesson_manager
from app import DEFAULT_TEACHER_FEEDBACK_TEMPLATES, app


class TeacherFeedbackApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        self.owner_token = payload["token"]
        self.owner_user = payload["user"]
        self.headers = {"X-Auth-Token": self.owner_token}

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def seed_owner_credits(self, amount: int = 20) -> None:
        credit_manager.apply_manual_adjustment(
            organization_id=self.owner_user["organization_id"],
            actor_user_id=self.owner_user["id"],
            amount=amount,
            note="seed feedback ai credits",
        )

    def create_lesson(self, *, class_id: int, topic: str = "Functions") -> int:
        return lesson_manager.save_lesson(
            date_str="2026-04-02",
            subject="Math",
            grade="Grade 9",
            topic=topic,
            summary="Worked through the key ideas from class.",
            weak_points="",
            plan={"lesson_info": {"topic": topic}},
            pdf_path="",
            class_id=class_id,
        )

    def approve_user(
        self,
        *,
        owner_token: str,
        username: str,
        display_name: str,
        password: str,
    ) -> dict:
        submit = self.client.post(
            "/api/register-request",
            json={
                "username": username,
                "display_name": display_name,
                "password": password,
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending_list = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(pending_list.status_code, 200)
        pending_payload = pending_list.get_json()
        self.assertIsNotNone(pending_payload)

        request_id = None
        for item in pending_payload["items"]:
            if item["username"] == username:
                request_id = item["id"]
                break
        self.assertIsNotNone(request_id)

        approve = self.client.post(
            f"/api/admin/registration-requests/{request_id}/approve",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(approve.status_code, 200)

        login = self.client.post(
            "/api/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(login.status_code, 200)
        payload = login.get_json()
        self.assertIsNotNone(payload)
        return payload

    def test_class_student_endpoints_create_number_and_remove_mapping_only(self):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")

        first = self.client.post(
            f"/api/classes/{class_id}/students",
            headers=self.headers,
            json={"name": "Alice"},
        )
        second = self.client.post(
            f"/api/classes/{class_id}/students",
            headers=self.headers,
            json={"name": "Alice"},
        )
        roster = self.client.get(
            f"/api/classes/{class_id}/students",
            headers=self.headers,
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        roster_names = [item["name"] for item in roster.get_json()["students"]]
        self.assertEqual(roster_names[0], "Alice")
        self.assertTrue(roster_names[1].startswith("Alice"))
        self.assertNotEqual(roster_names[1], "Alice")
        self.assertFalse(first.get_json()["deduplicated"])
        self.assertTrue(second.get_json()["deduplicated"])

        second_student_id = second.get_json()["student"]["id"]
        removed = self.client.delete(
            f"/api/classes/{class_id}/students/{second_student_id}",
            headers=self.headers,
        )
        roster_after = self.client.get(
            f"/api/classes/{class_id}/students",
            headers=self.headers,
        )

        self.assertEqual(removed.status_code, 200)
        self.assertTrue(removed.get_json()["removed"])
        self.assertEqual(
            [item["name"] for item in roster_after.get_json()["students"]],
            ["Alice"],
        )
        self.assertEqual(
            lesson_manager.get_student(second_student_id)["name"],
            roster_names[1],
        )

    def test_class_student_create_requires_non_empty_name(self):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")

        response = self.client.post(
            f"/api/classes/{class_id}/students",
            headers=self.headers,
            json={"name": "   "},
        )

        self.assertEqual(response.status_code, 400)

    def test_new_routes_require_authentication(self):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)

        responses = [
            self.client.get(f"/api/classes/{class_id}/students"),
            self.client.post(f"/api/classes/{class_id}/students", json={"name": "Alice"}),
            self.client.delete(f"/api/classes/{class_id}/students/1"),
            self.client.post(
                f"/api/lessons/{lesson_id}/feedback/draft",
                json={"students": [], "custom_templates": []},
            ),
            self.client.get(f"/api/lessons/{lesson_id}/feedback"),
            self.client.put(
                f"/api/lessons/{lesson_id}/feedback",
                json={"merged_text": "", "students": [], "custom_templates": []},
            ),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 401)

    def test_missing_class_and_lesson_return_404_on_new_routes(self):
        responses = [
            self.client.get("/api/classes/999999/students", headers=self.headers),
            self.client.post(
                "/api/classes/999999/students",
                headers=self.headers,
                json={"name": "Alice"},
            ),
            self.client.delete("/api/classes/999999/students/1", headers=self.headers),
            self.client.post(
                "/api/lessons/999999/feedback/draft",
                headers=self.headers,
                json={"students": [], "custom_templates": []},
            ),
            self.client.get("/api/lessons/999999/feedback", headers=self.headers),
            self.client.put(
                "/api/lessons/999999/feedback",
                headers=self.headers,
                json={"merged_text": "", "students": [], "custom_templates": []},
            ),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 404)

    def test_new_routes_reject_non_object_json_payloads(self):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)

        responses = [
            self.client.post(
                f"/api/classes/{class_id}/students",
                headers=self.headers,
                json=[],
            ),
            self.client.post(
                f"/api/lessons/{lesson_id}/feedback/draft",
                headers=self.headers,
                json=[],
            ),
            self.client.put(
                f"/api/lessons/{lesson_id}/feedback",
                headers=self.headers,
                json=[],
            ),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 400)

    @patch("app.generate_teacher_feedback_draft")
    def test_feedback_draft_returns_empty_when_no_students_selected(self, generate_teacher_feedback_draft):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)
        student = lesson_manager.create_student_for_class(class_id, "Alice")

        response = self.client.post(
            f"/api/lessons/{lesson_id}/feedback/draft",
            headers=self.headers,
            json={
                "students": [
                    {
                        "student_id": student["id"],
                        "selected_template_id": "",
                        "remark": "Keep reviewing the graph steps.",
                    }
                ],
                "custom_templates": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "lesson_id": lesson_id,
                "merged_text": "",
                "students_included": 0,
                "students_skipped": 1,
            },
        )
        generate_teacher_feedback_draft.assert_not_called()

    @patch("app.generate_teacher_feedback_draft")
    def test_feedback_draft_passes_builtin_template_details_to_ai(self, generate_teacher_feedback_draft):
        self.seed_owner_credits()
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)
        student = lesson_manager.create_student_for_class(class_id, "Alice")
        generate_teacher_feedback_draft.return_value = "Alice: classroom feedback"
        builtin_active = next(
            item for item in DEFAULT_TEACHER_FEEDBACK_TEMPLATES
            if item["id"] == "active"
        )

        response = self.client.post(
            f"/api/lessons/{lesson_id}/feedback/draft",
            headers=self.headers,
            json={
                "students": [
                    {
                        "student_id": student["id"],
                        "selected_template_id": "active",
                        "remark": "Explains steps clearly.",
                    }
                ],
                "custom_templates": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["students_included"], 1)
        self.assertEqual(response.get_json()["students_skipped"], 0)
        generate_teacher_feedback_draft.assert_called_once()

        call_kwargs = generate_teacher_feedback_draft.call_args.kwargs
        self.assertEqual(call_kwargs["lesson"]["id"], lesson_id)
        self.assertEqual(call_kwargs["students"][0]["name"], "Alice")
        self.assertEqual(call_kwargs["students"][0]["selected_template_id"], "active")
        self.assertEqual(call_kwargs["students"][0]["selected_template_label"], builtin_active["label"])
        self.assertEqual(call_kwargs["students"][0]["selected_template_guidance"], builtin_active["guidance"])
        self.assertEqual(call_kwargs["students"][0]["remark"], "Explains steps clearly.")

    @patch("app.generate_teacher_feedback_draft")
    def test_feedback_draft_passes_custom_template_details_to_ai(self, generate_teacher_feedback_draft):
        self.seed_owner_credits()
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)
        student = lesson_manager.create_student_for_class(class_id, "Alice")
        generate_teacher_feedback_draft.return_value = "Alice: classroom feedback"

        response = self.client.post(
            f"/api/lessons/{lesson_id}/feedback/draft",
            headers=self.headers,
            json={
                "students": [
                    {
                        "student_id": student["id"],
                        "selected_template_id": "custom-1",
                        "remark": "Retell the lesson once after class.",
                    }
                ],
                "custom_templates": [
                    {
                        "id": "custom-1",
                        "label": "Retell once after class",
                        "guidance": "Ask the student to retell the lesson once before homework.",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        generate_teacher_feedback_draft.assert_called_once()

        call_kwargs = generate_teacher_feedback_draft.call_args.kwargs
        self.assertEqual(call_kwargs["students"][0]["selected_template_label"], "Retell once after class")
        self.assertEqual(
            call_kwargs["students"][0]["selected_template_guidance"],
            "Ask the student to retell the lesson once before homework.",
        )

    @patch("app.generate_teacher_feedback_draft")
    def test_feedback_draft_skips_students_outside_the_current_roster(self, generate_teacher_feedback_draft):
        self.seed_owner_credits()
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)
        student = lesson_manager.create_student_for_class(class_id, "Alice")
        generate_teacher_feedback_draft.return_value = "Alice: classroom feedback"

        response = self.client.post(
            f"/api/lessons/{lesson_id}/feedback/draft",
            headers=self.headers,
            json={
                "students": [
                    {
                        "student_id": student["id"],
                        "selected_template_id": "active",
                        "remark": "Explains steps clearly.",
                    },
                    {
                        "student_id": 999999,
                        "name": "Ghost Student",
                        "selected_template_id": "active",
                        "remark": "Should not be included.",
                    },
                ],
                "custom_templates": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["students_included"], 1)
        self.assertEqual(response.get_json()["students_skipped"], 1)
        generate_teacher_feedback_draft.assert_called_once()
        call_kwargs = generate_teacher_feedback_draft.call_args.kwargs
        self.assertEqual([item["student_id"] for item in call_kwargs["students"]], [student["id"]])

    @patch("app.generate_teacher_feedback_draft")
    def test_feedback_draft_skips_students_when_class_roster_is_empty(self, generate_teacher_feedback_draft):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)

        response = self.client.post(
            f"/api/lessons/{lesson_id}/feedback/draft",
            headers=self.headers,
            json={
                "students": [
                    {
                        "student_id": 999999,
                        "name": "Ghost Student",
                        "selected_template_id": "active",
                        "remark": "Should not be included.",
                    }
                ],
                "custom_templates": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["students_included"], 0)
        self.assertEqual(response.get_json()["students_skipped"], 1)
        generate_teacher_feedback_draft.assert_not_called()

    @patch("app.generate_teacher_feedback_draft")
    def test_feedback_draft_skips_unknown_template_ids(self, generate_teacher_feedback_draft):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)
        student = lesson_manager.create_student_for_class(class_id, "Alice")

        response = self.client.post(
            f"/api/lessons/{lesson_id}/feedback/draft",
            headers=self.headers,
            json={
                "students": [
                    {
                        "student_id": student["id"],
                        "selected_template_id": "unknown-template",
                        "remark": "Should not be included.",
                    }
                ],
                "custom_templates": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["students_included"], 0)
        self.assertEqual(response.get_json()["students_skipped"], 1)
        generate_teacher_feedback_draft.assert_not_called()

    def test_feedback_save_defaults_student_index_from_students_when_omitted(self):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)
        student_a = lesson_manager.create_student_for_class(class_id, "Alice")
        student_b = lesson_manager.create_student_for_class(class_id, "Bob")

        save = self.client.put(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
            json={
                "merged_text": "Alice: edited feedback",
                "students": [
                    {
                        "student_id": student_a["id"],
                        "name": "Wrong Alice",
                        "selected_template_id": "active",
                        "remark": "Clear explanation.",
                    },
                    {
                        "student_id": student_b["id"],
                        "name": "Wrong Bob",
                        "selected_template_id": "",
                        "remark": "",
                    },
                ],
                "custom_templates": [],
            },
        )

        self.assertEqual(save.status_code, 200)
        self.assertEqual(
            save.get_json()["student_index"],
            [
                {"student_id": student_a["id"], "name": "Alice"},
                {"student_id": student_b["id"], "name": "Bob"},
            ],
        )

        reopened = self.client.get(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(
            reopened.get_json()["student_index"],
            [
                {"student_id": student_a["id"], "name": "Alice"},
                {"student_id": student_b["id"], "name": "Bob"},
            ],
        )

    def test_feedback_save_preserves_existing_editor_state_on_partial_updates(self):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)
        student = lesson_manager.create_student_for_class(class_id, "Alice")

        first_save = self.client.put(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
            json={
                "merged_text": "Alice: first version",
                "students": [
                    {
                        "student_id": student["id"],
                        "name": "Alice",
                        "selected_template_id": "active",
                        "remark": "Clear explanation.",
                    }
                ],
                "custom_templates": [
                    {
                        "id": "custom-1",
                        "label": "Retell once after class",
                        "guidance": "Ask the student to retell the lesson once before homework.",
                    }
                ],
            },
        )
        self.assertEqual(first_save.status_code, 200)

        partial_save = self.client.put(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
            json={"merged_text": "Alice: text-only update"},
        )

        self.assertEqual(partial_save.status_code, 200)
        self.assertEqual(
            partial_save.get_json()["student_index"],
            [{"student_id": student["id"], "name": "Alice"}],
        )

        reopened = self.client.get(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
        )
        reopened_payload = reopened.get_json()
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened_payload["merged_text"], "Alice: text-only update")
        self.assertEqual(reopened_payload["students"][0]["selected_template_id"], "active")
        self.assertEqual(reopened_payload["students"][0]["remark"], "Clear explanation.")
        self.assertEqual(reopened_payload["custom_templates"][0]["id"], "custom-1")

    def test_feedback_save_filters_ghost_students_and_unknown_template_ids(self):
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id)

        save = self.client.put(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
            json={
                "merged_text": "Ghost text should not create roster state",
                "students": [
                    {
                        "student_id": 999999,
                        "name": "Ghost Student",
                        "selected_template_id": "active",
                        "remark": "Should not be persisted.",
                    }
                ],
                "custom_templates": [
                    {
                        "id": "active",
                        "label": "Overridden",
                        "guidance": "Should be ignored.",
                    }
                ],
            },
        )

        self.assertEqual(save.status_code, 200)
        self.assertEqual(save.get_json()["student_index"], [])
        self.assertEqual(save.get_json()["editor_state"]["students"], [])
        self.assertEqual(save.get_json()["editor_state"]["custom_templates"], [])

        reopened = self.client.get(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
        )
        reopened_payload = reopened.get_json()
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened_payload["student_index"], [])
        self.assertEqual(reopened_payload["students"], [])
        self.assertEqual(reopened_payload["custom_templates"], [])

    @patch("app.generate_teacher_feedback_draft")
    def test_feedback_endpoints_save_and_reload_against_the_current_roster(self, generate_teacher_feedback_draft):
        self.seed_owner_credits()
        class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 9")
        lesson_id = self.create_lesson(class_id=class_id, topic="Function Graphs")
        student_a = lesson_manager.create_student_for_class(class_id, "Alice")
        student_b = lesson_manager.create_student_for_class(class_id, "Bob")
        generate_teacher_feedback_draft.return_value = "Alice: focus this week is function graphs"

        draft = self.client.post(
            f"/api/lessons/{lesson_id}/feedback/draft",
            headers=self.headers,
            json={
                "students": [
                    {
                        "student_id": student_a["id"],
                        "selected_template_id": "active",
                        "remark": "Explains steps clearly.",
                    },
                    {
                        "student_id": student_b["id"],
                        "selected_template_id": "",
                        "remark": "",
                    },
                ],
                "custom_templates": [],
            },
        )

        self.assertEqual(draft.status_code, 200)
        self.assertEqual(draft.get_json()["merged_text"], "Alice: focus this week is function graphs")
        self.assertEqual(draft.get_json()["students_included"], 1)
        self.assertEqual(draft.get_json()["students_skipped"], 1)

        save = self.client.put(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
            json={
                "merged_text": "Alice: edited feedback",
                "student_index": [{"student_id": student_a["id"], "name": "Alice"}],
                "students": [
                    {
                        "student_id": student_a["id"],
                        "name": "Alice",
                        "selected_template_id": "active",
                        "remark": "Explains steps clearly.",
                    },
                    {
                        "student_id": student_b["id"],
                        "name": "Bob",
                        "selected_template_id": "",
                        "remark": "",
                    },
                ],
                "custom_templates": [
                    {
                        "id": "custom-1",
                        "label": "Retell once after class",
                        "guidance": "Ask the student to retell the lesson once before homework.",
                    }
                ],
            },
        )

        self.assertEqual(save.status_code, 200)
        self.assertEqual(
            save.get_json()["student_index"],
            [{"student_id": student_a["id"], "name": "Alice"}],
        )
        self.assertEqual(save.get_json()["merged_text"], "Alice: edited feedback")

        lesson_manager.remove_student_from_class(class_id, student_b["id"])
        lesson_manager.create_student_for_class(class_id, "Carol")

        reopened = self.client.get(
            f"/api/lessons/{lesson_id}/feedback",
            headers=self.headers,
        )
        reopened_payload = reopened.get_json()

        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(
            reopened_payload["student_index"],
            [{"student_id": student_a["id"], "name": "Alice"}],
        )
        self.assertEqual(reopened_payload["merged_text"], "Alice: edited feedback")
        self.assertEqual(
            [item["name"] for item in reopened_payload["students"]],
            ["Alice", "Carol"],
        )
        self.assertEqual(reopened_payload["students"][0]["selected_template_id"], "active")
        self.assertEqual(reopened_payload["students"][1]["selected_template_id"], "")
        self.assertEqual(reopened_payload["custom_templates"][0]["id"], "custom-1")

    def test_member_gets_403_for_unassigned_class_and_lesson_feedback(self):
        member_payload = self.approve_user(
            owner_token=self.owner_token,
            username="feedback_member",
            display_name="Feedback Member",
            password="member123",
        )
        member_id = member_payload["user"]["id"]

        assigned_class_id = lesson_manager.save_class("Class Assigned", subject="Math", grade="Grade 9")
        other_class_id = lesson_manager.save_class("Class Other", subject="Math", grade="Grade 9")
        lesson_manager.set_user_class_ids(member_id, [assigned_class_id])

        assigned_student = lesson_manager.create_student_for_class(assigned_class_id, "Alice")
        lesson_manager.create_student_for_class(other_class_id, "Bob")

        assigned_lesson_id = self.create_lesson(class_id=assigned_class_id, topic="Functions")
        other_lesson_id = self.create_lesson(class_id=other_class_id, topic="Quadratics")

        member_headers = self.auth_headers(member_payload["token"])
        allowed_responses = [
            self.client.get(f"/api/classes/{assigned_class_id}/students", headers=member_headers),
            self.client.get(f"/api/lessons/{assigned_lesson_id}/feedback", headers=member_headers),
        ]
        denied_responses = [
            self.client.get(f"/api/classes/{other_class_id}/students", headers=member_headers),
            self.client.post(
                f"/api/classes/{other_class_id}/students",
                headers=member_headers,
                json={"name": "Carol"},
            ),
            self.client.delete(
                f"/api/classes/{other_class_id}/students/{assigned_student['id']}",
                headers=member_headers,
            ),
            self.client.post(
                f"/api/lessons/{other_lesson_id}/feedback/draft",
                headers=member_headers,
                json={"students": [], "custom_templates": []},
            ),
            self.client.get(f"/api/lessons/{other_lesson_id}/feedback", headers=member_headers),
            self.client.put(
                f"/api/lessons/{other_lesson_id}/feedback",
                headers=member_headers,
                json={"merged_text": "", "students": [], "custom_templates": []},
            ),
        ]

        for response in allowed_responses:
            self.assertEqual(response.status_code, 200)
        for response in denied_responses:
            self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
