import sys
import tempfile
import unittest
import gc
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
import master_data
import app as app_module
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
        gc.collect()
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

    def submit_organization_request(
        self,
        organization_name: str,
        username: str,
        display_name: str,
        password: str,
    ):
        return self.client.post(
            "/api/organization-requests",
            json={
                "organization_name": organization_name,
                "username": username,
                "display_name": display_name,
                "password": password,
            },
        )

    def approve_organization_request(self, super_owner_token: str, request_id: int):
        return self.client.post(
            f"/api/admin/organization-requests/{request_id}/approve",
            headers=self.auth_headers(super_owner_token),
        )

    def create_class(self, token: str, name: str, subject: str = "数学", grade: str = "初一"):
        return self.client.post(
            "/api/classes",
            headers=self.auth_headers(token),
            json={
                "name": name,
                "subject": subject,
                "grade": grade,
            },
        )

    def login_as_kayn(self) -> str:
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        payload = owner_login.get_json()
        self.assertIsNotNone(payload)
        return payload["token"]

    def create_approved_organization_with_invite(
        self,
        organization_name: str,
        owner_username: str,
        owner_display_name: str,
        owner_password: str,
    ) -> tuple[str, dict]:
        kayn_token = self.login_as_kayn()
        submit_response = self.submit_organization_request(
            organization_name=organization_name,
            username=owner_username,
            display_name=owner_display_name,
            password=owner_password,
        )
        self.assertEqual(submit_response.status_code, 201)
        submit_payload = submit_response.get_json()
        self.assertIsNotNone(submit_payload)
        request_id = submit_payload["id"]
        approve = self.client.post(
            f"/api/admin/organization-requests/{request_id}/approve",
            headers=self.auth_headers(kayn_token),
        )
        self.assertEqual(approve.status_code, 200)

        owner_login = self.client.post(
            "/api/login",
            json={"username": owner_username, "password": owner_password},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        owner_token = owner_payload["token"]

        invite_response = self.client.get(
            "/api/organization/invite",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(invite_response.status_code, 200)
        invite_payload = invite_response.get_json()
        self.assertIsNotNone(invite_payload)
        return owner_token, invite_payload

    def _token_from_invite_link(self, invite_link: str) -> str:
        parsed = urlparse(invite_link)
        return parsed.path.rsplit("/", 1)[-1]

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
        self.assertEqual(me_payload["username"], "kayn")
        self.assertEqual(me_payload["display_name"], "平台管理员")
        self.assertEqual(me_payload["role"], "super_owner")
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

    def test_backend_super_owner_approves_org_request_and_bootstraps_owner_and_invite(self):
        kayn_token = self.login_as_kayn()
        submit = self.client.post(
            "/api/organization-requests",
            json={
                "organization_name": "Beichen Academy",
                "username": "beichen_owner",
                "display_name": "Beichen Principal",
                "password": "secret123",
            },
        )
        self.assertEqual(submit.status_code, 201)
        request_id = submit.get_json()["id"]

        pending = self.client.get(
            "/api/admin/organization-requests",
            headers=self.auth_headers(kayn_token),
        )
        self.assertEqual(pending.status_code, 200)
        pending_payload = pending.get_json()
        self.assertIsNotNone(pending_payload)
        self.assertTrue(any(item["id"] == request_id for item in pending_payload["items"]))

        approve = self.client.post(
            f"/api/admin/organization-requests/{request_id}/approve",
            headers=self.auth_headers(kayn_token),
        )
        self.assertEqual(approve.status_code, 200)
        approved_payload = approve.get_json()
        self.assertIsNotNone(approved_payload)
        self.assertEqual(approved_payload["user"]["role"], "owner")
        self.assertEqual(approved_payload["user"]["organization_name"], "Beichen Academy")

        owner_login = self.client.post(
            "/api/login",
            json={"username": "beichen_owner", "password": "secret123"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)
        owner_token = owner_payload["token"]

        invite_response = self.client.get(
            "/api/organization/invite",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(invite_response.status_code, 200)
        invite_payload = invite_response.get_json()
        self.assertIsNotNone(invite_payload)
        self.assertEqual(invite_payload["organization_name"], "Beichen Academy")
        self.assertTrue(invite_payload["invite_code"])
        self.assertTrue(invite_payload["invite_link"])
        self.assertIn("/join/", invite_payload["invite_link"])

        conn = lesson_manager.get_conn()
        try:
            active_count = conn.execute(
                "SELECT COUNT(*) AS c FROM organization_invites WHERE organization_id=? AND status='active'",
                (approved_payload["user"]["organization_id"],),
            ).fetchone()["c"]
        finally:
            conn.close()
        self.assertEqual(active_count, 1)

    def test_backend_non_super_owner_cannot_approve_org_request(self):
        kayn_token = self.login_as_kayn()
        submit_response = self.submit_organization_request(
            organization_name="Forbidden Approver School",
            username="forbidden_owner",
            display_name="Forbidden Owner",
            password="forbidden123",
        )
        self.assertEqual(submit_response.status_code, 201)
        submit_payload = submit_response.get_json()
        self.assertIsNotNone(submit_payload)
        request_id = submit_payload["id"]

        owner_candidate_payload = self.approve_user(
            owner_token=kayn_token,
            username="owner_reviewer",
            display_name="Owner Reviewer",
            password="ownerreview123",
        )
        owner_candidate_me = self.client.get(
            "/api/me",
            headers=self.auth_headers(owner_candidate_payload["token"]),
        )
        self.assertEqual(owner_candidate_me.status_code, 200)
        owner_candidate_id = owner_candidate_me.get_json()["id"]

        promote = self.client.put(
            f"/api/admin/users/{owner_candidate_id}/role",
            headers=self.auth_headers(kayn_token),
            json={"role": "owner"},
        )
        self.assertEqual(promote.status_code, 200)

        pending_list = self.client.get(
            "/api/admin/organization-requests",
            headers=self.auth_headers(owner_candidate_payload["token"]),
        )
        self.assertEqual(pending_list.status_code, 403)

        approve = self.client.post(
            f"/api/admin/organization-requests/{request_id}/approve",
            headers=self.auth_headers(owner_candidate_payload["token"]),
        )
        self.assertEqual(approve.status_code, 403)

    def test_backend_join_by_invite_code_creates_active_member_in_target_org(self):
        _, invite_payload = self.create_approved_organization_with_invite(
            organization_name="Code Join School",
            owner_username="code_join_owner",
            owner_display_name="Code Join Owner",
            owner_password="ownerpass123",
        )

        join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": invite_payload["invite_code"],
                "username": "code_join_member",
                "display_name": "Code Join Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(join.status_code, 201)
        join_payload = join.get_json()
        self.assertIsNotNone(join_payload)
        self.assertEqual(join_payload["user"]["role"], "member")
        self.assertEqual(join_payload["user"]["status"], "active")
        self.assertEqual(join_payload["user"]["organization_name"], "Code Join School")

        member_login = self.client.post(
            "/api/login",
            json={"username": "code_join_member", "password": "memberpass123"},
        )
        self.assertEqual(member_login.status_code, 200)

    def test_backend_join_by_invite_link_creates_active_member_in_target_org(self):
        _, invite_payload = self.create_approved_organization_with_invite(
            organization_name="Link Join School",
            owner_username="link_join_owner",
            owner_display_name="Link Join Owner",
            owner_password="ownerpass123",
        )
        token = self._token_from_invite_link(invite_payload["invite_link"])

        preview = self.client.get(f"/api/invite/{token}")
        self.assertEqual(preview.status_code, 200)
        preview_payload = preview.get_json()
        self.assertIsNotNone(preview_payload)
        self.assertEqual(preview_payload["organization_name"], "Link Join School")

        join = self.client.post(
            f"/api/join-by-invite-link/{token}",
            json={
                "username": "link_join_member",
                "display_name": "Link Join Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(join.status_code, 201)
        join_payload = join.get_json()
        self.assertIsNotNone(join_payload)
        self.assertEqual(join_payload["user"]["role"], "member")
        self.assertEqual(join_payload["user"]["status"], "active")
        self.assertEqual(join_payload["user"]["organization_name"], "Link Join School")

    def test_backend_invite_reset_invalidates_old_code_and_link(self):
        owner_token, invite_payload = self.create_approved_organization_with_invite(
            organization_name="Reset Invite School",
            owner_username="reset_owner",
            owner_display_name="Reset Owner",
            owner_password="ownerpass123",
        )
        old_code = invite_payload["invite_code"]
        old_token = self._token_from_invite_link(invite_payload["invite_link"])

        reset = self.client.post(
            "/api/organization/invite/reset",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(reset.status_code, 200)
        new_invite_payload = reset.get_json()
        self.assertIsNotNone(new_invite_payload)
        self.assertNotEqual(new_invite_payload["invite_code"], old_code)
        self.assertNotEqual(
            self._token_from_invite_link(new_invite_payload["invite_link"]),
            old_token,
        )

        stale_code_join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": old_code,
                "username": "stale_code_member",
                "display_name": "Stale Code Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(stale_code_join.status_code, 404)

        stale_link_join = self.client.post(
            f"/api/join-by-invite-link/{old_token}",
            json={
                "username": "stale_link_member",
                "display_name": "Stale Link Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(stale_link_join.status_code, 404)

    def test_super_owner_approves_organization_request_and_bootstraps_owner_and_invite(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        submit = self.submit_organization_request(
            organization_name="Beichen Academy",
            username="beichen_owner",
            display_name="Beichen Principal",
            password="secret123",
        )
        self.assertEqual(submit.status_code, 201)
        submit_payload = submit.get_json()
        self.assertIsNotNone(submit_payload)
        request_id = submit_payload["id"]

        pending = self.client.get(
            "/api/admin/organization-requests",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(pending.status_code, 200)
        pending_payload = pending.get_json()
        self.assertIsNotNone(pending_payload)
        self.assertEqual(pending_payload["items"][0]["organization_name"], "Beichen Academy")

        approve = self.approve_organization_request(owner_token, request_id)
        self.assertEqual(approve.status_code, 200)
        approve_payload = approve.get_json()
        self.assertIsNotNone(approve_payload)
        self.assertEqual(approve_payload["user"]["role"], "owner")
        self.assertEqual(approve_payload["user"]["organization_name"], "Beichen Academy")

        organization_owner_login = self.client.post(
            "/api/login",
            json={"username": "beichen_owner", "password": "secret123"},
        )
        self.assertEqual(organization_owner_login.status_code, 200)
        organization_owner_token = organization_owner_login.get_json()["token"]

        invite = self.client.get(
            "/api/organization/invite",
            headers=self.auth_headers(organization_owner_token),
        )
        self.assertEqual(invite.status_code, 200)
        invite_payload = invite.get_json()
        self.assertIsNotNone(invite_payload)
        self.assertEqual(invite_payload["organization_name"], "Beichen Academy")
        self.assertTrue(invite_payload["invite_code"])
        self.assertTrue(invite_payload["invite_link"])

    def test_non_super_owner_cannot_approve_organization_requests(self):
        super_owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(super_owner_login.status_code, 200)
        super_owner_token = super_owner_login.get_json()["token"]

        submit = self.submit_organization_request(
            organization_name="Xinghe School",
            username="xinghe_owner",
            display_name="Xinghe Owner",
            password="ownerpass123",
        )
        self.assertEqual(submit.status_code, 201)
        request_id = submit.get_json()["id"]

        owner_payload = self.approve_user(
            owner_token=super_owner_token,
            username="org_review_owner",
            display_name="Org Review Owner",
            password="review123",
        )
        owner_id = self.client.get(
            "/api/me",
            headers=self.auth_headers(owner_payload["token"]),
        ).get_json()["id"]
        promote = self.client.put(
            f"/api/admin/users/{owner_id}/role",
            headers=self.auth_headers(super_owner_token),
            json={"role": "owner"},
        )
        self.assertEqual(promote.status_code, 200)

        forbidden = self.approve_organization_request(owner_payload["token"], request_id)
        self.assertEqual(forbidden.status_code, 403)

    def test_owner_only_sees_members_classes_and_requests_from_own_organization(self):
        kayn_token = self.login_as_kayn()
        alpha_owner_token, _ = self.create_approved_organization_with_invite(
            organization_name="Alpha School",
            owner_username="alpha_owner",
            owner_display_name="Alpha Owner",
            owner_password="ownerpass123",
        )
        beta_owner_token, _ = self.create_approved_organization_with_invite(
            organization_name="Beta School",
            owner_username="beta_owner",
            owner_display_name="Beta Owner",
            owner_password="ownerpass123",
        )

        alpha_join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": self.client.get(
                    "/api/organization/invite",
                    headers=self.auth_headers(alpha_owner_token),
                ).get_json()["invite_code"],
                "username": "alpha_member",
                "display_name": "Alpha Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(alpha_join.status_code, 201)

        beta_join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": self.client.get(
                    "/api/organization/invite",
                    headers=self.auth_headers(beta_owner_token),
                ).get_json()["invite_code"],
                "username": "beta_member",
                "display_name": "Beta Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(beta_join.status_code, 201)

        starain_pending = self.client.post(
            "/api/register-request",
            json={
                "username": "starain_pending",
                "display_name": "Starain Pending",
                "password": "pending123",
                "organization_name": "星润Starain",
            },
        )
        self.assertEqual(starain_pending.status_code, 201)

        alpha_class = self.create_class(alpha_owner_token, "Alpha 一班")
        self.assertEqual(alpha_class.status_code, 201)

        beta_class = self.create_class(beta_owner_token, "Beta 一班")
        self.assertEqual(beta_class.status_code, 201)

        alpha_users = self.client.get("/api/admin/users", headers=self.auth_headers(alpha_owner_token))
        self.assertEqual(alpha_users.status_code, 200)
        alpha_user_names = {item["name"] for item in alpha_users.get_json()}
        self.assertEqual(alpha_user_names, {"Alpha Owner", "Alpha Member"})
        self.assertEqual({item["org"] for item in alpha_users.get_json()}, {"Alpha School"})

        alpha_classes = self.client.get("/api/classes", headers=self.auth_headers(alpha_owner_token))
        self.assertEqual(alpha_classes.status_code, 200)
        self.assertEqual({item["name"] for item in alpha_classes.get_json()}, {"Alpha 一班"})

        alpha_requests = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(alpha_owner_token),
        )
        self.assertEqual(alpha_requests.status_code, 200)
        self.assertEqual(alpha_requests.get_json()["items"], [])

    def test_super_owner_can_list_registered_organizations(self):
        kayn_token = self.login_as_kayn()
        alpha_owner_token, _ = self.create_approved_organization_with_invite(
            organization_name="Alpha School",
            owner_username="alpha_owner",
            owner_display_name="Alpha Owner",
            owner_password="ownerpass123",
        )
        self.create_class(alpha_owner_token, "Alpha 一班")

        organizations = self.client.get(
            "/api/admin/organizations",
            headers=self.auth_headers(kayn_token),
        )
        self.assertEqual(organizations.status_code, 200)
        payload = organizations.get_json()
        self.assertIsInstance(payload, dict)
        names = {item["name"] for item in payload["items"]}
        self.assertIn("星润Starain", names)
        self.assertIn("Alpha School", names)
        alpha_item = next(item for item in payload["items"] if item["name"] == "Alpha School")
        self.assertGreaterEqual(alpha_item["member_count"], 1)
        self.assertGreaterEqual(alpha_item["owner_count"], 1)
        self.assertGreaterEqual(alpha_item["class_count"], 1)

    def test_owner_can_update_member_display_name_in_own_organization(self):
        owner_token, invite = self.create_approved_organization_with_invite(
            organization_name="Alpha School",
            owner_username="alpha_owner",
            owner_display_name="Alpha Owner",
            owner_password="ownerpass123",
        )
        join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": invite["invite_code"],
                "username": "alpha_member",
                "display_name": "Alpha Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(join.status_code, 201)
        member_id = join.get_json()["user"]["id"]

        update = self.client.put(
            f"/api/admin/users/{member_id}/profile",
            headers=self.auth_headers(owner_token),
            json={"display_name": "Alpha Member Renamed"},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()["user"]["display_name"], "Alpha Member Renamed")

        users = self.client.get("/api/admin/users", headers=self.auth_headers(owner_token))
        self.assertEqual(users.status_code, 200)
        renamed = next(item for item in users.get_json() if item["id"] == member_id)
        self.assertEqual(renamed["name"], "Alpha Member Renamed")

    def test_owner_cannot_update_member_display_name_in_other_organization(self):
        alpha_owner_token, _ = self.create_approved_organization_with_invite(
            organization_name="Alpha School",
            owner_username="alpha_owner",
            owner_display_name="Alpha Owner",
            owner_password="ownerpass123",
        )
        beta_owner_token, beta_invite = self.create_approved_organization_with_invite(
            organization_name="Beta School",
            owner_username="beta_owner",
            owner_display_name="Beta Owner",
            owner_password="ownerpass123",
        )
        join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": beta_invite["invite_code"],
                "username": "beta_member",
                "display_name": "Beta Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(join.status_code, 201)
        beta_member_id = join.get_json()["user"]["id"]

        forbidden = self.client.put(
            f"/api/admin/users/{beta_member_id}/profile",
            headers=self.auth_headers(alpha_owner_token),
            json={"display_name": "Should Fail"},
        )
        self.assertEqual(forbidden.status_code, 404)

        beta_users = self.client.get("/api/admin/users", headers=self.auth_headers(beta_owner_token))
        self.assertEqual(beta_users.status_code, 200)
        beta_member = next(item for item in beta_users.get_json() if item["id"] == beta_member_id)
        self.assertEqual(beta_member["name"], "Beta Member")

    def test_members_can_join_by_invite_code_and_old_invites_fail_after_reset(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        submit = self.submit_organization_request(
            organization_name="Xinghe School",
            username="xinghe_owner",
            display_name="Xinghe Owner",
            password="ownerpass123",
        )
        self.assertEqual(submit.status_code, 201)
        request_id = submit.get_json()["id"]

        approve = self.approve_organization_request(owner_token, request_id)
        self.assertEqual(approve.status_code, 200)

        organization_owner_login = self.client.post(
            "/api/login",
            json={"username": "xinghe_owner", "password": "ownerpass123"},
        )
        self.assertEqual(organization_owner_login.status_code, 200)
        organization_owner_token = organization_owner_login.get_json()["token"]

        invite = self.client.get(
            "/api/organization/invite",
            headers=self.auth_headers(organization_owner_token),
        )
        self.assertEqual(invite.status_code, 200)
        invite_payload = invite.get_json()
        self.assertIsNotNone(invite_payload)

        join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": invite_payload["invite_code"],
                "username": "teacher_joined",
                "display_name": "Teacher Joined",
                "password": "joinpass123",
            },
        )
        self.assertEqual(join.status_code, 201)
        join_payload = join.get_json()
        self.assertIsNotNone(join_payload)
        self.assertEqual(join_payload["user"]["organization_name"], "Xinghe School")
        self.assertEqual(join_payload["user"]["role"], "member")

        reset = self.client.post(
            "/api/organization/invite/reset",
            headers=self.auth_headers(organization_owner_token),
        )
        self.assertEqual(reset.status_code, 200)
        reset_payload = reset.get_json()
        self.assertIsNotNone(reset_payload)
        self.assertNotEqual(reset_payload["invite_code"], invite_payload["invite_code"])

        stale_join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": invite_payload["invite_code"],
                "username": "teacher_old_code",
                "display_name": "Teacher Old Code",
                "password": "joinpass123",
            },
        )
        self.assertEqual(stale_join.status_code, 404)

        next_join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": reset_payload["invite_code"],
                "username": "teacher_new_code",
                "display_name": "Teacher New Code",
                "password": "joinpass123",
            },
        )
        self.assertEqual(next_join.status_code, 201)

    def test_members_can_join_by_invite_link(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        submit = self.submit_organization_request(
            organization_name="Tianqi International",
            username="tianqi_owner",
            display_name="Tianqi Owner",
            password="ownerpass123",
        )
        self.assertEqual(submit.status_code, 201)
        request_id = submit.get_json()["id"]

        approve = self.approve_organization_request(owner_token, request_id)
        self.assertEqual(approve.status_code, 200)

        organization_owner_login = self.client.post(
            "/api/login",
            json={"username": "tianqi_owner", "password": "ownerpass123"},
        )
        self.assertEqual(organization_owner_login.status_code, 200)
        organization_owner_token = organization_owner_login.get_json()["token"]

        invite = self.client.get(
            "/api/organization/invite",
            headers=self.auth_headers(organization_owner_token),
        )
        self.assertEqual(invite.status_code, 200)
        invite_payload = invite.get_json()
        self.assertIsNotNone(invite_payload)
        invite_token = invite_payload["invite_link"].rsplit("/", 1)[-1]

        invite_lookup = self.client.get(f"/api/invite/{invite_token}")
        self.assertEqual(invite_lookup.status_code, 200)
        self.assertEqual(invite_lookup.get_json()["organization_name"], "Tianqi International")

        join = self.client.post(
            f"/api/join-by-invite-link/{invite_token}",
            json={
                "username": "teacher_linked",
                "display_name": "Teacher Linked",
                "password": "joinpass123",
            },
        )
        self.assertEqual(join.status_code, 201)
        join_payload = join.get_json()
        self.assertIsNotNone(join_payload)
        self.assertEqual(join_payload["user"]["organization_name"], "Tianqi International")
    def test_kayn_login_maps_to_reserved_owner_account(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_payload = owner_login.get_json()
        self.assertIsNotNone(owner_payload)

        me = self.client.get(
            "/api/me",
            headers=self.auth_headers(owner_payload["token"]),
        )
        self.assertEqual(me.status_code, 200)
        me_payload = me.get_json()
        self.assertEqual(me_payload["username"].lower(), "kayn")
        self.assertEqual(me_payload["role"], "super_owner")

        duplicate_submit = self.client.post(
            "/api/register-request",
            json={
                "username": "kayn",
                "display_name": "Fake Kayn",
                "password": "secret123",
                "organization_name": "星润Starain",
            },
        )
        self.assertEqual(duplicate_submit.status_code, 409)

    def test_owner_username_cannot_be_changed_away_from_kayn(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        rename_response = self.client.put(
            "/api/profile",
            headers=self.auth_headers(owner_token),
            json={"username": "other_owner", "display_name": "Other Owner"},
        )
        self.assertEqual(rename_response.status_code, 409)

    def test_only_super_owner_can_assign_owner_role(self):
        super_owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(super_owner_login.status_code, 200)
        super_owner_token = super_owner_login.get_json()["token"]

        owner_candidate_payload = self.approve_user(
            owner_token=super_owner_token,
            username="owner_candidate",
            display_name="Owner Candidate",
            password="ownerpass123",
        )
        owner_candidate_me = self.client.get(
            "/api/me",
            headers=self.auth_headers(owner_candidate_payload["token"]),
        )
        self.assertEqual(owner_candidate_me.status_code, 200)
        owner_candidate_id = owner_candidate_me.get_json()["id"]

        promote_owner = self.client.put(
            f"/api/admin/users/{owner_candidate_id}/role",
            headers=self.auth_headers(super_owner_token),
            json={"role": "owner"},
        )
        self.assertEqual(promote_owner.status_code, 200)

        owner_me_after_promote = self.client.get(
            "/api/me",
            headers=self.auth_headers(owner_candidate_payload["token"]),
        )
        self.assertEqual(owner_me_after_promote.status_code, 200)
        self.assertEqual(owner_me_after_promote.get_json()["role"], "owner")

        pending_submit = self.client.post(
            "/api/register-request",
            json={
                "username": "pending_teacher",
                "display_name": "Pending Teacher",
                "password": "pending123",
                "organization_name": "星润Starain",
            },
        )
        self.assertEqual(pending_submit.status_code, 201)

        owner_pending_list = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(owner_candidate_payload["token"]),
        )
        self.assertEqual(owner_pending_list.status_code, 200)

        member_candidate_payload = self.approve_user(
            owner_token=owner_candidate_payload["token"],
            username="member_candidate",
            display_name="Member Candidate",
            password="memberpass123",
        )
        member_candidate_me = self.client.get(
            "/api/me",
            headers=self.auth_headers(member_candidate_payload["token"]),
        )
        self.assertEqual(member_candidate_me.status_code, 200)
        member_candidate_id = member_candidate_me.get_json()["id"]

        owner_promote_owner = self.client.put(
            f"/api/admin/users/{member_candidate_id}/role",
            headers=self.auth_headers(owner_candidate_payload["token"]),
            json={"role": "owner"},
        )
        self.assertEqual(owner_promote_owner.status_code, 403)
        owner_promote_admin = self.client.put(
            f"/api/admin/users/{member_candidate_id}/role",
            headers=self.auth_headers(owner_candidate_payload["token"]),
            json={"role": "admin"},
        )
        self.assertEqual(owner_promote_admin.status_code, 200)

        member_after_promote = self.client.get(
            "/api/me",
            headers=self.auth_headers(member_candidate_payload["token"]),
        )
        self.assertEqual(member_after_promote.status_code, 200)
        self.assertEqual(member_after_promote.get_json()["role"], "admin")

    def test_staff_can_view_member_binding_summary(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        teacher_payload = self.approve_user(
            owner_token=owner_token,
            username="teacher_binding_a",
            display_name="Teacher Binding A",
            password="teacher123",
        )
        teacher_id = teacher_payload["user"]["id"]

        class_id = lesson_manager.save_class("六年级 1 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, teacher_id)
        master_data.upsert_wrong_question_mapping(
            "record-binding-1",
            teacher_user_id=teacher_id,
            class_id=class_id,
            teacher_name_snapshot="Teacher Binding A",
            class_name_snapshot="六年级1班",
            subject_snapshot="数学",
            mapping_status="mapped",
        )

        response = self.client.get(
            "/api/admin/member-binding-summary",
            headers=self.auth_headers(owner_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        summary_by_user_id = {item["user_id"]: item for item in payload["items"]}
        teacher_summary = summary_by_user_id[teacher_id]
        self.assertEqual(teacher_summary["mini_teacher_bound"], True)
        self.assertEqual(teacher_summary["responsible_classes"], [{"id": class_id, "name": "六年级 1 班"}])
        self.assertEqual(teacher_summary["mapping_summary"]["status"], "healthy")
        self.assertEqual(teacher_summary["mapping_summary"]["mapped_count"], 1)
        self.assertEqual(teacher_summary["mapping_summary"]["needs_review_count"], 0)

    def test_member_binding_summary_marks_stale_teacher_rebinding_as_needs_review(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        original_teacher = self.approve_user(
            owner_token=owner_token,
            username="teacher_binding_old",
            display_name="Teacher Binding Old",
            password="teacher123",
        )
        replacement_teacher = self.approve_user(
            owner_token=owner_token,
            username="teacher_binding_new",
            display_name="Teacher Binding New",
            password="teacher123",
        )
        original_teacher_id = original_teacher["user"]["id"]
        replacement_teacher_id = replacement_teacher["user"]["id"]

        class_id = lesson_manager.save_class("六年级 6 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, original_teacher_id)
        master_data.upsert_wrong_question_mapping(
            "record-binding-stale-1",
            teacher_user_id=original_teacher_id,
            class_id=class_id,
            teacher_name_snapshot="Teacher Binding Old",
            class_name_snapshot="六年级6班",
            subject_snapshot="数学",
            mapping_status="mapped",
        )
        lesson_manager.set_class_teacher_user_id(class_id, replacement_teacher_id)

        response = self.client.get(
            "/api/admin/member-binding-summary",
            headers=self.auth_headers(owner_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        summary_by_user_id = {item["user_id"]: item for item in payload["items"]}
        original_summary = summary_by_user_id[original_teacher_id]
        self.assertEqual(original_summary["mapping_summary"]["status"], "needs_review")
        self.assertEqual(original_summary["mapping_summary"]["needs_review_count"], 1)
        self.assertEqual(original_summary["mini_teacher_bound"], True)

    def test_member_cannot_view_member_binding_summary(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        member_payload = self.approve_user(
            owner_token=owner_token,
            username="binding_member",
            display_name="Binding Member",
            password="member123",
        )

        response = self.client.get(
            "/api/admin/member-binding-summary",
            headers=self.auth_headers(member_payload["token"]),
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_access_master_data_binding_endpoints(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        admin_payload = self.approve_user(
            owner_token=owner_token,
            username="binding_admin",
            display_name="Binding Admin",
            password="admin123",
        )
        admin_id = admin_payload["user"]["id"]
        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        queue_response = self.client.get(
            "/api/master-data/mappings/wrong-questions",
            headers=self.auth_headers(admin_payload["token"]),
        )
        self.assertEqual(queue_response.status_code, 403)

        alias_get = self.client.get(
            "/api/master-data/users/1/aliases",
            headers=self.auth_headers(admin_payload["token"]),
        )
        self.assertEqual(alias_get.status_code, 403)

        alias_put = self.client.put(
            "/api/master-data/users/1/aliases",
            headers=self.auth_headers(admin_payload["token"]),
            json={"aliases": ["Kayn老师"]},
        )
        self.assertEqual(alias_put.status_code, 403)

    def test_member_wrong_question_list_is_scoped_to_owned_teacher_and_classes(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        target_member = self.approve_user(
            owner_token=owner_token,
            username="wrong_member_a",
            display_name="Wrong Member A",
            password="member123",
        )
        target_member_id = target_member["user"]["id"]
        other_member = self.approve_user(
            owner_token=owner_token,
            username="wrong_member_b",
            display_name="Wrong Member B",
            password="member123",
        )
        other_member_id = other_member["user"]["id"]

        owned_class_id = lesson_manager.save_class("六年级 1 班", subject="数学", grade="六年级")
        other_class_id = lesson_manager.save_class("初一 2 班", subject="英语", grade="初一")
        lesson_manager.set_class_teacher_user_id(owned_class_id, target_member_id)
        lesson_manager.set_class_teacher_user_id(other_class_id, other_member_id)

        downstream_payload = {
            "items": [
                {
                    "id": "record-owned-teacher",
                    "student_name": "Alice",
                    "class_name": "未分班",
                    "class_id": None,
                    "subject": "数学",
                    "teacher_name": "Wrong Member A",
                    "teacher_user_id": target_member_id,
                    "mapping_status": "mapped",
                    "created_at": "2026-04-01T10:00:00Z",
                    "analysis": {
                        "question_category": "计算",
                        "error_type": "计算错误",
                        "knowledge_points": ["分数运算"],
                        "is_repeated_mistake": "是",
                        "teacher_priority": "高",
                    },
                },
                {
                    "id": "record-owned-class",
                    "student_name": "Bob",
                    "class_name": "六年级 1 班",
                    "class_id": owned_class_id,
                    "subject": "数学",
                    "teacher_name": "代课老师",
                    "teacher_user_id": None,
                    "mapping_status": "needs_review",
                    "created_at": "2026-04-01T11:00:00Z",
                    "analysis": {
                        "question_category": "应用题",
                        "error_type": "审题错误",
                        "knowledge_points": ["列式"],
                        "is_repeated_mistake": "否",
                        "teacher_priority": "中",
                    },
                },
                {
                    "id": "record-other",
                    "student_name": "Cathy",
                    "class_name": "初一 2 班",
                    "class_id": other_class_id,
                    "subject": "英语",
                    "teacher_name": "Wrong Member B",
                    "teacher_user_id": other_member_id,
                    "mapping_status": "mapped",
                    "created_at": "2026-04-01T12:00:00Z",
                    "analysis": {
                        "question_category": "阅读",
                        "error_type": "定位错误",
                        "knowledge_points": ["细节定位"],
                        "is_repeated_mistake": "是",
                        "teacher_priority": "高",
                        "selected_error_type": "定位错误",
                    },
                },
            ],
            "summary": {
                "total_count": 3,
                "repeated_mistake_count": 2,
                "high_priority_count": 2,
                "pending_review_count": 2,
            },
        }

        with patch.object(app_module.smart_wrong_questions, "fetch_wrong_question_records", return_value=downstream_payload):
            response = self.client.get(
                "/api/wrong-questions",
                headers=self.auth_headers(target_member["token"]),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual([item["id"] for item in payload["items"]], ["record-owned-teacher", "record-owned-class"])
        self.assertEqual(
            payload["summary"],
            {
                "total_count": 2,
                "repeated_mistake_count": 1,
                "high_priority_count": 1,
                "pending_review_count": 2,
            },
        )

    def test_member_cannot_access_unrelated_wrong_question_detail_or_review(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        target_member = self.approve_user(
            owner_token=owner_token,
            username="wrong_detail_member",
            display_name="Wrong Detail Member",
            password="member123",
        )
        other_member = self.approve_user(
            owner_token=owner_token,
            username="wrong_detail_other",
            display_name="Wrong Detail Other",
            password="member123",
        )
        other_member_id = other_member["user"]["id"]

        other_class_id = lesson_manager.save_class("高一 3 班", subject="物理", grade="高一")
        lesson_manager.set_class_teacher_user_id(other_class_id, other_member_id)

        unrelated_record = {
            "id": "record-unrelated",
            "student_name": "Dana",
            "class_name": "高一 3 班",
            "class_id": other_class_id,
            "subject": "物理",
            "teacher_name": "Wrong Detail Other",
            "teacher_user_id": other_member_id,
            "mapping_status": "mapped",
            "created_at": "2026-04-01T13:00:00Z",
            "analysis": {
                "question_category": "受力",
                "error_type": "模型错误",
                "knowledge_points": ["受力分析"],
            },
        }

        with patch.object(app_module.smart_wrong_questions, "fetch_wrong_question_record", return_value=unrelated_record):
            detail_response = self.client.get(
                "/api/wrong-questions/record-unrelated",
                headers=self.auth_headers(target_member["token"]),
            )

        self.assertEqual(detail_response.status_code, 404)

        with patch.object(app_module.smart_wrong_questions, "fetch_wrong_question_record", return_value=unrelated_record), patch.object(app_module.smart_wrong_questions, "save_wrong_question_review") as save_review:
            review_response = self.client.put(
                "/api/wrong-questions/record-unrelated/review",
                headers=self.auth_headers(target_member["token"]),
                json={"selectedErrorType": "模型错误"},
            )

        self.assertEqual(review_response.status_code, 404)
        save_review.assert_not_called()

    def test_member_lessons_list_only_returns_owned_class_records(self):
        owner_token = self.login_as_kayn()

        target_member = self.approve_user(
            owner_token=owner_token,
            username="lesson_member_a",
            display_name="Lesson Member A",
            password="member123",
        )
        target_member_id = target_member["user"]["id"]
        other_member = self.approve_user(
            owner_token=owner_token,
            username="lesson_member_b",
            display_name="Lesson Member B",
            password="member123",
        )
        other_member_id = other_member["user"]["id"]

        owned_class_id = lesson_manager.save_class("Class A", subject="Math", grade="Grade 6")
        other_class_id = lesson_manager.save_class("Class B", subject="English", grade="Grade 7")
        lesson_manager.set_class_teacher_user_id(owned_class_id, target_member_id)
        lesson_manager.set_class_teacher_user_id(other_class_id, other_member_id)

        owned_lesson_id = lesson_manager.save_lesson(
            "2026-04-02",
            "Math",
            "Grade 6",
            "Fractions",
            "summary",
            "weak",
            {"questions": []},
            "",
            owned_class_id,
        )
        lesson_manager.save_lesson(
            "2026-04-02",
            "English",
            "Grade 7",
            "Reading",
            "summary",
            "weak",
            {"questions": []},
            "",
            other_class_id,
        )
        lesson_manager.save_lesson(
            "2026-04-02",
            "Science",
            "Grade 8",
            "Legacy No Class",
            "summary",
            "weak",
            {"questions": []},
            "",
            0,
        )

        response = self.client.get(
            "/api/lessons",
            headers=self.auth_headers(target_member["token"]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual([item["id"] for item in payload], [owned_lesson_id])

    def test_member_cannot_access_unowned_lesson_detail_delete_or_pdf(self):
        owner_token = self.login_as_kayn()

        target_member = self.approve_user(
            owner_token=owner_token,
            username="lesson_detail_member",
            display_name="Lesson Detail Member",
            password="member123",
        )
        target_member_id = target_member["user"]["id"]
        other_member = self.approve_user(
            owner_token=owner_token,
            username="lesson_detail_other",
            display_name="Lesson Detail Other",
            password="member123",
        )
        other_member_id = other_member["user"]["id"]

        owned_class_id = lesson_manager.save_class("Owned Class", subject="Physics", grade="Grade 10")
        other_class_id = lesson_manager.save_class("Other Class", subject="Physics", grade="Grade 10")
        lesson_manager.set_class_teacher_user_id(owned_class_id, target_member_id)
        lesson_manager.set_class_teacher_user_id(other_class_id, other_member_id)

        detail_delete_lesson_id = lesson_manager.save_lesson(
            "2026-04-02",
            "Physics",
            "Grade 10",
            "Kinematics",
            "summary",
            "weak",
            {"questions": []},
            "",
            other_class_id,
        )

        pdf_path = self.base / "restricted.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%fake pdf\n")

        pdf_lesson_id = lesson_manager.save_lesson(
            "2026-04-02",
            "Physics",
            "Grade 10",
            "Momentum",
            "summary",
            "weak",
            {"questions": []},
            str(pdf_path),
            other_class_id,
        )

        detail_response = self.client.get(
            f"/api/lessons/{detail_delete_lesson_id}",
            headers=self.auth_headers(target_member["token"]),
        )
        preview_response = self.client.get(
            f"/api/pdf/{pdf_lesson_id}",
            headers=self.auth_headers(target_member["token"]),
        )
        download_response = self.client.get(
            f"/api/pdf/download/{pdf_lesson_id}",
            headers=self.auth_headers(target_member["token"]),
        )
        delete_response = self.client.delete(
            f"/api/lessons/{detail_delete_lesson_id}",
            headers=self.auth_headers(target_member["token"]),
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(preview_response.status_code, 404)
        self.assertEqual(download_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)

    def test_member_lesson_creation_requires_owned_class(self):
        owner_token = self.login_as_kayn()

        target_member = self.approve_user(
            owner_token=owner_token,
            username="lesson_create_member",
            display_name="Lesson Create Member",
            password="member123",
        )
        other_member = self.approve_user(
            owner_token=owner_token,
            username="lesson_create_other",
            display_name="Lesson Create Other",
            password="member123",
        )
        target_member_id = target_member["user"]["id"]
        other_member_id = other_member["user"]["id"]

        owned_class_id = lesson_manager.save_class("Owned Create Class", subject="Chemistry", grade="Grade 9")
        other_class_id = lesson_manager.save_class("Other Create Class", subject="Chemistry", grade="Grade 9")
        lesson_manager.set_class_teacher_user_id(owned_class_id, target_member_id)
        lesson_manager.set_class_teacher_user_id(other_class_id, other_member_id)

        with patch("app.has_api_key", return_value=True), \
             patch("ai_processor.parse_and_generate_plan", return_value={"questions": []}), \
             patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf"):
            missing_class_response = self.client.post(
                "/api/lessons",
                headers=self.auth_headers(target_member["token"]),
                json={
                    "subject": "Chemistry",
                    "topic": "Acid Base",
                    "date": "2026-04-02",
                    "weak_points": "equations",
                    "summary_text": "class summary",
                    "input_type": "text",
                },
            )
            forbidden_class_response = self.client.post(
                "/api/lessons",
                headers=self.auth_headers(target_member["token"]),
                json={
                    "subject": "Chemistry",
                    "class_id": other_class_id,
                    "topic": "Acid Base",
                    "date": "2026-04-02",
                    "weak_points": "equations",
                    "summary_text": "class summary",
                    "input_type": "text",
                },
            )
            allowed_class_response = self.client.post(
                "/api/lessons",
                headers=self.auth_headers(target_member["token"]),
                json={
                    "subject": "Chemistry",
                    "class_id": owned_class_id,
                    "topic": "Acid Base",
                    "date": "2026-04-02",
                    "weak_points": "equations",
                    "summary_text": "class summary",
                    "input_type": "text",
                },
            )

        self.assertEqual(missing_class_response.status_code, 400)
        self.assertEqual(forbidden_class_response.status_code, 403)
        self.assertEqual(allowed_class_response.status_code, 201)

    def test_owner_and_admin_still_have_full_lesson_visibility(self):
        owner_token = self.login_as_kayn()

        admin_member = self.approve_user(
            owner_token=owner_token,
            username="lesson_admin_scope",
            display_name="Lesson Admin Scope",
            password="member123",
        )
        admin_id = admin_member["user"]["id"]
        promote = self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote.status_code, 200)

        class_member_a = self.approve_user(
            owner_token=owner_token,
            username="lesson_scope_helper_a",
            display_name="Lesson Scope Helper A",
            password="member123",
        )
        class_member_b = self.approve_user(
            owner_token=owner_token,
            username="lesson_scope_helper_b",
            display_name="Lesson Scope Helper B",
            password="member123",
        )
        class_a = lesson_manager.save_class("Owner Scope Class", subject="Biology", grade="Grade 11")
        class_b = lesson_manager.save_class("Admin Scope Class", subject="Biology", grade="Grade 11")
        lesson_manager.set_class_teacher_user_id(class_a, class_member_a["user"]["id"])
        lesson_manager.set_class_teacher_user_id(class_b, class_member_b["user"]["id"])

        lesson_a_id = lesson_manager.save_lesson(
            "2026-04-02",
            "Biology",
            "Grade 11",
            "Cell",
            "summary",
            "weak",
            {"questions": []},
            "",
            class_a,
        )
        lesson_b_id = lesson_manager.save_lesson(
            "2026-04-02",
            "Biology",
            "Grade 11",
            "Genetics",
            "summary",
            "weak",
            {"questions": []},
            "",
            class_b,
        )

        owner_response = self.client.get("/api/lessons", headers=self.auth_headers(owner_token))
        admin_response = self.client.get("/api/lessons", headers=self.auth_headers(admin_member["token"]))

        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(admin_response.status_code, 200)
        owner_payload = owner_response.get_json()
        admin_payload = admin_response.get_json()
        self.assertIsNotNone(owner_payload)
        self.assertIsNotNone(admin_payload)
        self.assertCountEqual([item["id"] for item in owner_payload], [lesson_a_id, lesson_b_id])
        self.assertCountEqual([item["id"] for item in admin_payload], [lesson_a_id, lesson_b_id])

    def test_owner_can_access_master_data_binding_endpoints(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        owner_payload = self.approve_user(
            owner_token=owner_token,
            username="binding_owner",
            display_name="Binding Owner",
            password="owner123",
        )
        owner_id = owner_payload["user"]["id"]
        promote = self.client.put(
            f"/api/admin/users/{owner_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "owner"},
        )
        self.assertEqual(promote.status_code, 200)

        queue_response = self.client.get(
            "/api/master-data/mappings/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )
        self.assertEqual(queue_response.status_code, 200)

        alias_put = self.client.put(
            "/api/master-data/users/1/aliases",
            headers=self.auth_headers(owner_payload["token"]),
            json={"aliases": ["Kayn老师"]},
        )
        self.assertEqual(alias_put.status_code, 200)
        self.assertEqual(alias_put.get_json()["aliases"], ["Kayn老师"])

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
