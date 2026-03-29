import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
import smart_wrong_questions
from app import app


class FakeResponse:
    def __init__(self, raw: bytes, headers: dict[str, str] | None = None):
        self._raw = raw
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._raw


class SmartWrongQuestionsApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config(
            {
                "wrong_question_service_url": "http://wrong-question-service.local",
                "wrong_question_service_token": "teacher-token-1",
            }
        )
        lesson_manager.init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def approve_user(self, owner_token: str, username: str, display_name: str, password: str) -> dict:
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
        payload = login.get_json()
        self.assertIsNotNone(payload)
        return payload

    def login_owner(self) -> dict:
        response = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        return payload

    def test_member_cannot_access_wrong_question_routes(self):
        owner_payload = self.login_owner()
        member_payload = self.approve_user(
            owner_token=owner_payload["token"],
            username="member_wrong_question",
            display_name="Member Wrong Question",
            password="member123",
        )

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(member_payload["token"]),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "无权限")

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_staff_can_list_wrong_question_records(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        fetch_wrong_question_records.return_value = {
            "items": [
                {
                    "id": "record-1",
                    "student_name": "Alice",
                    "subject": "Math",
                }
            ],
            "total": 1,
        }

        response = self.client.get(
            "/api/wrong-questions?studentName=Alice&page=1&pageSize=20&empty=",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 1)
        self.assertEqual(response.get_json()["items"][0]["id"], "record-1")
        fetch_wrong_question_records.assert_called_once()
        forwarded_args = fetch_wrong_question_records.call_args.args[0]
        self.assertEqual(forwarded_args.get("studentName"), "Alice")
        self.assertEqual(forwarded_args.get("page"), "1")
        self.assertEqual(forwarded_args.get("pageSize"), "20")
        self.assertEqual(forwarded_args.get("empty"), "")

    @patch("smart_wrong_questions.fetch_wrong_question_record")
    def test_staff_can_get_wrong_question_record_detail(self, fetch_wrong_question_record):
        owner_payload = self.login_owner()
        fetch_wrong_question_record.return_value = {
            "id": "record-42",
            "student_name": "Alice",
            "question_text": "2 + 2 = ?",
        }

        response = self.client.get(
            "/api/wrong-questions/record-42?studentName=Alice&subject=Math",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], "record-42")
        fetch_wrong_question_record.assert_called_once()
        self.assertEqual(fetch_wrong_question_record.call_args.args[0], "record-42")
        forwarded_args = fetch_wrong_question_record.call_args.args[1]
        self.assertEqual(forwarded_args.get("studentName"), "Alice")
        self.assertEqual(forwarded_args.get("subject"), "Math")

    @patch("smart_wrong_questions.save_wrong_question_review")
    def test_staff_can_save_wrong_question_review(self, save_wrong_question_review):
        owner_payload = self.login_owner()
        save_wrong_question_review.return_value = {
            "ok": True,
            "record": {"id": "record-42", "teacher_comment": "需要重做"},
        }

        response = self.client.put(
            "/api/wrong-questions/record-42/review?teacherName=Kayn",
            headers=self.auth_headers(owner_payload["token"]),
            json={"teacher_comment": "需要重做", "mastery": "needs_practice"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        save_wrong_question_review.assert_called_once()
        self.assertEqual(save_wrong_question_review.call_args.args[0], "record-42")
        forwarded_args = save_wrong_question_review.call_args.args[1]
        forwarded_payload = save_wrong_question_review.call_args.args[2]
        self.assertEqual(forwarded_args.get("teacherName"), "Kayn")
        self.assertEqual(
            forwarded_payload,
            {"teacher_comment": "需要重做", "mastery": "needs_practice"},
        )

    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_list_route_translates_config_proxy_errors(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        fetch_wrong_question_records.side_effect = smart_wrong_questions.WrongQuestionProxyError(
            "智能错题服务尚未配置",
            503,
        )

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"error": "智能错题服务尚未配置"})

    @patch("smart_wrong_questions.save_wrong_question_review")
    def test_review_route_translates_downstream_proxy_errors(self, save_wrong_question_review):
        owner_payload = self.login_owner()
        save_wrong_question_review.side_effect = smart_wrong_questions.WrongQuestionProxyError(
            "下游服务不可用: timeout",
            502,
        )

        response = self.client.put(
            "/api/wrong-questions/record-42/review",
            headers=self.auth_headers(owner_payload["token"]),
            json={"teacher_comment": "需要重做"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "下游服务不可用: timeout"})

    @patch("smart_wrong_questions.request.urlopen")
    def test_malformed_downstream_json_becomes_proxy_error(self, urlopen):
        urlopen.return_value = FakeResponse(b"not-json")

        with self.assertRaises(smart_wrong_questions.WrongQuestionProxyError) as ctx:
            smart_wrong_questions.fetch_wrong_question_records({"studentName": "Alice"})

        self.assertEqual(str(ctx.exception), "下游服务返回了无效响应")
        self.assertEqual(ctx.exception.status_code, 502)

    @patch("smart_wrong_questions.export_wrong_question_summary")
    def test_export_route_returns_pdf_attachment(self, export_wrong_question_summary):
        owner_payload = self.login_owner()
        export_wrong_question_summary.return_value = {
            "content": b"%PDF-1.4\nmock pdf\n",
            "filename": "wrong-question-summary.pdf",
        }

        response = self.client.get(
            "/api/wrong-questions/summary/export?studentName=Alice",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn(
            'attachment; filename=wrong-question-summary.pdf',
            response.headers.get("Content-Disposition", ""),
        )
        self.assertEqual(response.data, b"%PDF-1.4\nmock pdf\n")
        export_wrong_question_summary.assert_called_once()
        forwarded_args = export_wrong_question_summary.call_args.args[0]
        self.assertEqual(forwarded_args.get("studentName"), "Alice")


if __name__ == "__main__":
    unittest.main()