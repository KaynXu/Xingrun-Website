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


class AccountFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def approve_user(
        self,
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
                "organization_name": "星润Starain",
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
        login_payload = login.get_json()
        self.assertIsNotNone(login_payload)
        return login_payload

    def test_owner_seed_and_approval_flow(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        owner_token = owner_payload["token"]

        me = self.client.get("/api/me", headers=self.auth_headers(owner_token))
        self.assertEqual(me.status_code, 200)
        me_payload = me.get_json()
        self.assertEqual(me_payload["username"], "Kayn")
        self.assertEqual(me_payload["role"], "owner")
        self.assertEqual(me_payload["organization_name"], "星润Starain")

        submit = self.client.post(
            "/api/register-request",
            json={
                "username": "teacher_a",
                "display_name": "Teacher A",
                "password": "secret123",
                "organization_name": "星润Starain",
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending_login = self.client.post(
            "/api/login",
            json={"username": "teacher_a", "password": "secret123"},
        )
        self.assertEqual(pending_login.status_code, 401)

        pending_list = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(pending_list.status_code, 200)
        pending_payload = pending_list.get_json()
        self.assertEqual(len(pending_payload["items"]), 1)
        request_id = pending_payload["items"][0]["id"]

        approve = self.client.post(
            f"/api/admin/registration-requests/{request_id}/approve",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(approve.status_code, 200)

        member_login = self.client.post(
            "/api/login",
            json={"username": "teacher_a", "password": "secret123"},
        )
        self.assertEqual(member_login.status_code, 200)
        member_payload = member_login.get_json()
        self.assertIsNotNone(member_payload)

        member_me = self.client.get(
            "/api/me",
            headers=self.auth_headers(member_payload["token"]),
        )
        self.assertEqual(member_me.status_code, 200)
        member_me_payload = member_me.get_json()
        self.assertEqual(member_me_payload["role"], "member")
        self.assertEqual(member_me_payload["organization_name"], "星润Starain")

    def test_anonymous_users_cannot_access_backend_apis(self):
        stats = self.client.get("/api/stats")
        self.assertEqual(stats.status_code, 401)

        classes = self.client.get("/api/classes")
        self.assertEqual(classes.status_code, 401)

    def test_admin_can_manage_classes_and_assign_member_assignments(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        owner_token = owner_payload["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_a",
            display_name="Admin A",
            password="adminpass123",
        )
        admin_token = admin_payload["token"]
        admin_me = self.client.get("/api/me", headers=self.auth_headers(admin_token))
        self.assertEqual(admin_me.status_code, 200)
        admin_me_payload = admin_me.get_json()
        self.assertIsNotNone(admin_me_payload)
        admin_id = admin_me_payload["id"]

        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        member_payload = self.approve_user(
            owner_token=owner_token,
            username="member_a",
            display_name="Member A",
            password="memberpass123",
        )
        member_token = member_payload["token"]
        member_me = self.client.get("/api/me", headers=self.auth_headers(member_token))
        self.assertEqual(member_me.status_code, 200)
        member_me_payload = member_me.get_json()
        self.assertIsNotNone(member_me_payload)
        member_id = member_me_payload["id"]

        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(admin_token),
            json={
                "name": "六年级数学冲刺班",
                "subject": "数学",
                "grade": "六年级",
            },
        )
        self.assertEqual(create_class.status_code, 201)
        create_class_payload = create_class.get_json()
        self.assertIsNotNone(create_class_payload)
        class_id = create_class_payload["id"]

        assign_classes = self.client.put(
            f"/api/admin/users/{member_id}/classes",
            headers=self.auth_headers(admin_token),
            json={"class_ids": [class_id]},
        )
        self.assertEqual(assign_classes.status_code, 200)

        member_classes = self.client.get(
            f"/api/admin/users/{member_id}/classes",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(member_classes.status_code, 200)
        member_classes_payload = member_classes.get_json()
        self.assertIsNotNone(member_classes_payload)
        self.assertEqual(member_classes_payload["class_ids"], [class_id])

        admin_pending_requests = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(admin_pending_requests.status_code, 403)

        admin_role_update = self.client.put(
            f"/api/admin/users/{member_id}/role",
            headers=self.auth_headers(admin_token),
            json={"role": "admin"},
        )
        self.assertEqual(admin_role_update.status_code, 403)

    def test_admin_rejects_null_class_ids_payload(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_null",
            display_name="Admin Null",
            password="adminnull123",
        )
        admin_token = admin_payload["token"]
        admin_me = self.client.get("/api/me", headers=self.auth_headers(admin_token))
        admin_id = admin_me.get_json()["id"]

        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        member_payload = self.approve_user(
            owner_token=owner_token,
            username="member_null",
            display_name="Member Null",
            password="membernull123",
        )
        member_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(member_payload["token"]),
        ).get_json()["id"]

        assign_classes = self.client.put(
            f"/api/admin/users/{member_id}/classes",
            headers=self.auth_headers(admin_token),
            json={"class_ids": None},
        )
        self.assertEqual(assign_classes.status_code, 400)
        self.assertEqual(assign_classes.get_json()["error"], "class_ids must be a list")

    def test_admin_assigning_nonexistent_class_returns_404(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_missing_class",
            display_name="Admin Missing Class",
            password="adminmissing123",
        )
        admin_token = admin_payload["token"]
        admin_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(admin_token),
        ).get_json()["id"]
        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        member_payload = self.approve_user(
            owner_token=owner_token,
            username="member_missing_class",
            display_name="Member Missing Class",
            password="membermissing123",
        )
        member_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(member_payload["token"]),
        ).get_json()["id"]

        assign_classes = self.client.put(
            f"/api/admin/users/{member_id}/classes",
            headers=self.auth_headers(admin_token),
            json={"class_ids": [999999]},
        )
        self.assertEqual(assign_classes.status_code, 404)
        self.assertEqual(assign_classes.get_json()["error"], "class not found: 999999")

    def test_admin_assigning_nonexistent_user_returns_404(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_missing_user",
            display_name="Admin Missing User",
            password="adminmissinguser123",
        )
        admin_token = admin_payload["token"]
        admin_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(admin_token),
        ).get_json()["id"]
        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        assign_classes = self.client.put(
            "/api/admin/users/999999/classes",
            headers=self.auth_headers(admin_token),
            json={"class_ids": []},
        )
        self.assertEqual(assign_classes.status_code, 404)
        self.assertEqual(assign_classes.get_json()["error"], "user not found")

    def test_delete_class_clears_assignments_and_unlinks_lessons(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_delete_class",
            display_name="Admin Delete Class",
            password="admindelete123",
        )
        admin_token = admin_payload["token"]
        admin_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(admin_token),
        ).get_json()["id"]
        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        member_payload = self.approve_user(
            owner_token=owner_token,
            username="member_delete_class",
            display_name="Member Delete Class",
            password="memberdelete123",
        )
        member_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(member_payload["token"]),
        ).get_json()["id"]

        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(admin_token),
            json={
                "name": "六年级英语冲刺班",
                "subject": "英语",
                "grade": "六年级",
            },
        )
        self.assertEqual(create_class.status_code, 201)
        class_id = create_class.get_json()["id"]

        assign_classes = self.client.put(
            f"/api/admin/users/{member_id}/classes",
            headers=self.auth_headers(admin_token),
            json={"class_ids": [class_id]},
        )
        self.assertEqual(assign_classes.status_code, 200)

        lesson_id = lesson_manager.save_lesson(
            date_str="2026-03-29",
            subject="英语",
            grade="六年级",
            topic="阅读理解",
            summary="课堂总结",
            weak_points="",
            plan={"questions": []},
            pdf_path="",
            class_id=class_id,
        )

        lesson_manager.delete_class(class_id)

        self.assertEqual(lesson_manager.get_user_class_ids(member_id), [])
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertIsNotNone(lesson)
        self.assertIsNone(lesson["class_id"])

    def test_staff_can_bind_single_teacher_to_class_and_sync_teacher_name(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_teacher_bind",
            display_name="Admin Teacher Bind",
            password="adminteacher123",
        )
        admin_token = admin_payload["token"]
        admin_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(admin_token),
        ).get_json()["id"]
        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        teacher_payload = self.approve_user(
            owner_token=owner_token,
            username="teacher_bind_a",
            display_name="Teacher Bind A",
            password="teacherbind123",
        )
        teacher_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(teacher_payload["token"]),
        ).get_json()["id"]

        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(admin_token),
            json={
                "name": "六年级 2 班",
                "subject": "数学",
                "grade": "六年级",
                "teacher_name": "",
                "teacher_email": "",
            },
        )
        self.assertEqual(create_class.status_code, 201)
        class_id = create_class.get_json()["id"]

        bind_teacher = self.client.put(
            f"/api/classes/{class_id}/teacher",
            headers=self.auth_headers(admin_token),
            json={"teacher_user_id": teacher_id},
        )
        self.assertEqual(bind_teacher.status_code, 200)

        class_detail = self.client.get(
            f"/api/classes/{class_id}",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(class_detail.status_code, 200)
        class_payload = class_detail.get_json()
        self.assertEqual(class_payload["teacher_name"], "Teacher Bind A")
        self.assertEqual(class_payload["teacher_user_id"], teacher_id)

        teacher_bindings = self.client.get(
            "/api/classes/teacher-bindings",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(teacher_bindings.status_code, 200)
        self.assertEqual(
            teacher_bindings.get_json()["teacher_bindings"],
            {str(class_id): teacher_id},
        )

    def test_rebinding_class_replaces_previous_teacher_relation(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_teacher_swap",
            display_name="Admin Teacher Swap",
            password="adminswap123",
        )
        admin_token = admin_payload["token"]
        admin_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(admin_token),
        ).get_json()["id"]
        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        teacher_a = self.approve_user(
            owner_token=owner_token,
            username="teacher_swap_a",
            display_name="Teacher Swap A",
            password="teachera123",
        )
        teacher_b = self.approve_user(
            owner_token=owner_token,
            username="teacher_swap_b",
            display_name="Teacher Swap B",
            password="teacherb123",
        )
        teacher_a_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(teacher_a["token"]),
        ).get_json()["id"]
        teacher_b_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(teacher_b["token"]),
        ).get_json()["id"]

        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(admin_token),
            json={
                "name": "初一 1 班",
                "subject": "英语",
                "grade": "初一",
                "teacher_name": "",
                "teacher_email": "",
            },
        )
        self.assertEqual(create_class.status_code, 201)
        class_id = create_class.get_json()["id"]

        first_bind = self.client.put(
            f"/api/classes/{class_id}/teacher",
            headers=self.auth_headers(admin_token),
            json={"teacher_user_id": teacher_a_id},
        )
        self.assertEqual(first_bind.status_code, 200)

        second_bind = self.client.put(
            f"/api/classes/{class_id}/teacher",
            headers=self.auth_headers(admin_token),
            json={"teacher_user_id": teacher_b_id},
        )
        self.assertEqual(second_bind.status_code, 200)

        teacher_a_classes = self.client.get(
            f"/api/admin/users/{teacher_a_id}/classes",
            headers=self.auth_headers(admin_token),
        )
        teacher_b_classes = self.client.get(
            f"/api/admin/users/{teacher_b_id}/classes",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(teacher_a_classes.status_code, 200)
        self.assertEqual(teacher_b_classes.status_code, 200)
        self.assertEqual(teacher_a_classes.get_json()["class_ids"], [])
        self.assertEqual(teacher_b_classes.get_json()["class_ids"], [class_id])

        class_detail = self.client.get(
            f"/api/classes/{class_id}",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(class_detail.status_code, 200)
        class_payload = class_detail.get_json()
        self.assertEqual(class_payload["teacher_name"], "Teacher Swap B")
        self.assertEqual(class_payload["teacher_user_id"], teacher_b_id)

    def test_legacy_class_update_preserves_bound_teacher_identity_when_fields_omitted(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="admin_legacy_update",
            display_name="Admin Legacy Update",
            password="adminlegacy123",
        )
        admin_token = admin_payload["token"]
        admin_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(admin_token),
        ).get_json()["id"]
        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        teacher_payload = self.approve_user(
            owner_token=owner_token,
            username="teacher_legacy_update",
            display_name="Teacher Legacy Update",
            password="teacherlegacy123",
        )
        teacher_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(teacher_payload["token"]),
        ).get_json()["id"]

        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(admin_token),
            json={
                "name": "高一 1 班",
                "subject": "物理",
                "grade": "高一",
                "teacher_name": "",
                "teacher_email": "",
            },
        )
        self.assertEqual(create_class.status_code, 201)
        class_id = create_class.get_json()["id"]

        bind_teacher = self.client.put(
            f"/api/classes/{class_id}/teacher",
            headers=self.auth_headers(admin_token),
            json={"teacher_user_id": teacher_id},
        )
        self.assertEqual(bind_teacher.status_code, 200)

        legacy_update = self.client.put(
            f"/api/classes/{class_id}",
            headers=self.auth_headers(admin_token),
            json={
                "name": "高一 1 班提高班",
                "subject": "物理",
                "grade": "高一",
            },
        )
        self.assertEqual(legacy_update.status_code, 200)

        class_detail = self.client.get(
            f"/api/classes/{class_id}",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(class_detail.status_code, 200)
        class_payload = class_detail.get_json()
        self.assertEqual(class_payload["name"], "高一 1 班提高班")
        self.assertEqual(class_payload["teacher_name"], "Teacher Legacy Update")
        self.assertEqual(class_payload["teacher_user_id"], teacher_id)

    def test_member_cannot_write_class_management_apis(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        owner_token = owner_payload["token"]

        member_payload = self.approve_user(
            owner_token=owner_token,
            username="member_b",
            display_name="Member B",
            password="memberpass456",
        )
        member_token = member_payload["token"]

        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(member_token),
            json={
                "name": "六年级数学基础班",
                "subject": "数学",
                "grade": "六年级",
            },
        )
        self.assertEqual(create_class.status_code, 403)

        admin_users = self.client.get(
            "/api/admin/users",
            headers=self.auth_headers(member_token),
        )
        self.assertEqual(admin_users.status_code, 403)


if __name__ == "__main__":
    unittest.main()
