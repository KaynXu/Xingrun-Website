from __future__ import annotations

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
from app import app


class WeChatParentUploadApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({"wechat_service_token": "wechat-service-token"})
        lesson_manager.init_db()
        self.client = app.test_client()

        self.owner_payload = self.login_owner()
        self.owner_id = self.owner_payload["user"]["id"]
        self.class_id = lesson_manager.save_class(
            "六年级 1 班",
            subject="数学",
            grade="六年级",
            organization_id=self.owner_payload["user"]["organization_id"],
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner_id)
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")
        self.invite = lesson_manager.get_or_create_active_class_invite(self.class_id, self.owner_id)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    @staticmethod
    def service_headers() -> dict[str, str]:
        return {"X-Wechat-Service-Token": "wechat-service-token"}

    @staticmethod
    def recognized_payload(*, is_geometry: bool = False, question_text: str = "计算 $2+3\\times4$ 的结果。") -> dict:
        return {
            "is_geometry": is_geometry,
            "question_text": "" if is_geometry else question_text,
            "confidence": "high",
            "notes": "几何图形题" if is_geometry else "",
        }

    def login_owner(self) -> dict:
        response = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        return payload

    def test_owner_can_view_and_reset_class_invite(self):
        invite = self.client.get(
            f"/api/classes/{self.class_id}/invite",
            headers=self.auth_headers(self.owner_payload["token"]),
        )
        reset = self.client.post(
            f"/api/classes/{self.class_id}/invite/reset",
            headers=self.auth_headers(self.owner_payload["token"]),
        )

        self.assertEqual(invite.status_code, 200)
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(invite.get_json()["class_id"], self.class_id)
        self.assertNotEqual(invite.get_json()["invite_code"], reset.get_json()["invite_code"])

    def test_wechat_service_can_login_bind_and_upload(self):
        login = self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()["account"]["openid"], "openid-1")

        bind_preview = self.client.post(
            "/api/wechat/bind-class",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "invite_code": self.invite["invite_code"]},
        )
        self.assertEqual(bind_preview.status_code, 200)
        self.assertEqual(bind_preview.get_json()["class_id"], self.class_id)
        self.assertEqual(bind_preview.get_json()["students"][0]["name"], "Alice")

        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        binding = bind.get_json()["binding"]

        with patch("app.ai_processor.recognize_wrong_question_image", return_value=self.recognized_payload()), \
             patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf"):
            upload = self.client.post(
                "/api/wechat/wrong-questions",
                headers=self.service_headers(),
                json={
                    "open_id": "openid-1",
                    "binding_id": binding["id"],
                    "image_url": "https://files.example.com/record.png",
                    "child_raw_reason_text": "我把乘法和加法一起从左往右算了",
                    "primary_error_type": "方法问题",
                    "secondary_error_summary": "先算了加法，忽略乘法优先",
                },
            )

        self.assertEqual(upload.status_code, 201)
        record = upload.get_json()["record"]
        self.assertEqual(record["source"], "wechat_mp")
        self.assertEqual(record["teacher_user_id"], self.owner_id)
        self.assertEqual(record["class_id"], self.class_id)
        self.assertEqual(record["student_id"], self.student["id"])
        self.assertEqual(record["recognition_status"], "recognized")
        self.assertEqual(record["child_raw_reason_text"], "我把乘法和加法一起从左往右算了")
        self.assertEqual(record["primary_error_type"], "方法问题")
        self.assertEqual(record["secondary_error_summary"], "先算了加法，忽略乘法优先")
        self.assertEqual(record["student_library_pdf_path"], "/tmp/student-1.pdf")

    def test_wechat_service_can_fetch_latest_parent_bindings(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)

        bindings = self.client.get(
            "/api/wechat/bindings",
            headers=self.service_headers(),
            query_string={"open_id": "openid-1"},
        )

        self.assertEqual(bindings.status_code, 200)
        payload = bindings.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["bindings"]), 1)
        self.assertEqual(payload["bindings"][0]["class_name"], "六年级 1 班")
        self.assertEqual(payload["bindings"][0]["student_name"], "Alice")
        self.assertEqual(payload["bindings"][0]["teacher_name"], "平台管理员")

    def test_wechat_service_upload_requires_child_reason_text(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        binding = bind.get_json()["binding"]

        with patch("app.ai_processor.recognize_wrong_question_image", return_value=self.recognized_payload()), \
             patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf"):
            upload = self.client.post(
                "/api/wechat/wrong-questions",
                headers=self.service_headers(),
                json={
                    "open_id": "openid-1",
                    "binding_id": binding["id"],
                    "image_url": "https://files.example.com/record.png",
                },
            )

        self.assertEqual(upload.status_code, 400)
        self.assertEqual(upload.get_json()["error"], "child_raw_reason_text is required")

    def test_wechat_service_can_transcribe_child_reason_audio(self):
        with patch(
            "app.ai_processor.transcribe_child_reason_audio",
            return_value={"transcript_text": "我把乘法和加法一起从左往右算了"},
        ) as transcribe_mock:
            response = self.client.post(
                "/api/wechat/reason-transcriptions",
                headers=self.service_headers(),
                json={"audio_url": "https://files.example.com/reason.m4a"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["transcript_text"], "我把乘法和加法一起从左往右算了")
        transcribe_mock.assert_called_once_with("https://files.example.com/reason.m4a")

    def test_wechat_service_can_classify_child_reason_text(self):
        with patch(
            "app.ai_processor.classify_wrong_question_reason",
            return_value={
                "display_text": "方法问题｜先算了加法，忽略乘法优先",
                "primary_error_type": "方法问题",
                "secondary_error_summary": "先算了加法，忽略乘法优先",
            },
        ) as classify_mock:
            response = self.client.post(
                "/api/wechat/reason-classifications",
                headers=self.service_headers(),
                json={"child_reason_text": "我把乘法和加法一起从左往右算了"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["display_text"], "方法问题｜先算了加法，忽略乘法优先")
        self.assertEqual(payload["primary_error_type"], "方法问题")
        self.assertEqual(payload["secondary_error_summary"], "先算了加法，忽略乘法优先")
        classify_mock.assert_called_once_with("我把乘法和加法一起从左往右算了")

    def test_wechat_service_no_longer_exposes_wrong_question_box_detection(self):
        response = self.client.post(
            "/api/wechat/wrong-question-boxes",
            headers=self.service_headers(),
            json={"image_url": "https://files.example.com/worksheet.png"},
        )

        self.assertEqual(response.status_code, 404)

    def test_wechat_upload_persists_finalized_reason_fields_without_reclassifying(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        binding = bind.get_json()["binding"]

        with patch("app.ai_processor.recognize_wrong_question_image", return_value=self.recognized_payload()), \
             patch("app.ai_processor.classify_wrong_question_reason") as classify_mock, \
             patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf"):
            upload = self.client.post(
                "/api/wechat/wrong-questions",
                headers=self.service_headers(),
                json={
                    "open_id": "openid-1",
                    "binding_id": binding["id"],
                    "image_url": "https://files.example.com/record.png",
                    "child_raw_reason_text": "我看漏了题目里要先把米换成厘米",
                    "child_reason_input_mode": "voice",
                    "primary_error_type": "审题问题",
                    "secondary_error_summary": "看漏了先换算单位这一步",
                },
            )

        self.assertEqual(upload.status_code, 201)
        record = upload.get_json()["record"]
        self.assertEqual(record["child_raw_reason_text"], "我看漏了题目里要先把米换成厘米")
        self.assertEqual(record["child_reason_input_mode"], "voice")
        self.assertEqual(record["primary_error_type"], "审题问题")
        self.assertEqual(record["secondary_error_summary"], "看漏了先换算单位这一步")
        classify_mock.assert_not_called()

    def test_parent_child_library_lists_only_bound_student_records(self):
        second_student = lesson_manager.create_student_for_class(self.class_id, "Bob")

        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        first_binding_response = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(first_binding_response.status_code, 200)
        first_binding = first_binding_response.get_json()["binding"]

        second_binding_response = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": second_student["id"],
            },
        )
        self.assertEqual(second_binding_response.status_code, 200)
        second_binding = second_binding_response.get_json()["binding"]

        with patch("app.ai_processor.recognize_wrong_question_image", return_value=self.recognized_payload()), \
             patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf"):
            first_upload = self.client.post(
                "/api/wechat/wrong-questions",
                headers=self.service_headers(),
                json={
                    "open_id": "openid-1",
                    "binding_id": first_binding["id"],
                    "image_url": "https://files.example.com/record-1.png",
                    "child_raw_reason_text": "我把乘法放到最后算了",
                    "primary_error_type": "方法问题",
                    "secondary_error_summary": "运算顺序放错了位置",
                },
            )
        self.assertEqual(first_upload.status_code, 201)

        with patch("app.ai_processor.recognize_wrong_question_image", return_value=self.recognized_payload()), \
             patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-2.pdf"):
            second_upload = self.client.post(
                "/api/wechat/wrong-questions",
                headers=self.service_headers(),
                json={
                    "open_id": "openid-1",
                    "binding_id": second_binding["id"],
                    "image_url": "https://files.example.com/record-2.png",
                    "child_raw_reason_text": "我没看明白题目让求什么",
                    "primary_error_type": "审题问题",
                    "secondary_error_summary": "没看清题目到底要求什么",
                },
            )
        self.assertEqual(second_upload.status_code, 201)

        response = self.client.get(
            f"/api/wechat/children/{self.student['id']}/wrong-questions",
            headers=self.service_headers(),
            query_string={"open_id": "openid-1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["student_id"], self.student["id"])
        self.assertEqual(payload["items"][0]["id"], first_upload.get_json()["record"]["id"])

    @patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf")
    @patch("app.ai_processor.recognize_wrong_question_image")
    def test_wechat_upload_requires_successful_non_geometry_recognition(self, mock_recognize, mock_rebuild):
        mock_recognize.return_value = self.recognized_payload()

        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        binding = bind.get_json()["binding"]

        response = self.client.post(
            "/api/wechat/wrong-questions",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "binding_id": binding["id"],
                "image_url": "https://files.example.com/record.png",
                "child_raw_reason_text": "我把乘法放到最后算了",
                "primary_error_type": "方法问题",
                "secondary_error_summary": "运算顺序放错了位置",
            },
        )

        self.assertEqual(response.status_code, 201)
        record = response.get_json()["record"]
        self.assertEqual(record["recognition_status"], "recognized")
        self.assertEqual(record["question_text"], "计算 $2+3\\times4$ 的结果。")
        self.assertEqual(record["student_library_pdf_path"], "/tmp/student-1.pdf")
        self.assertEqual(response.get_json()["student_library_pdf_url"], f"/api/wechat/student-libraries/{self.student['id']}")
        mock_rebuild.assert_called_once_with(self.student["id"])

    @patch("app.ai_processor.recognize_wrong_question_image", side_effect=ValueError("题目识别失败，请重新识别"))
    def test_wechat_upload_rejects_failed_non_geometry_recognition(self, _mock_recognize):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        binding = bind.get_json()["binding"]

        response = self.client.post(
            "/api/wechat/wrong-questions",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "binding_id": binding["id"],
                "image_url": "https://files.example.com/record.png",
                "child_raw_reason_text": "我把乘法放到最后算了",
                "primary_error_type": "方法问题",
                "secondary_error_summary": "运算顺序放错了位置",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], "题目识别失败，请重新识别")
        self.assertEqual(lesson_manager.list_wechat_wrong_question_submissions(), [])

    @patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf")
    @patch("app.ai_processor.recognize_wrong_question_image")
    def test_wechat_child_library_endpoint_returns_shared_pdf_url(self, mock_recognize, _mock_rebuild):
        mock_recognize.return_value = self.recognized_payload(is_geometry=True)

        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        binding = bind.get_json()["binding"]
        upload = self.client.post(
            "/api/wechat/wrong-questions",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "binding_id": binding["id"],
                "image_url": "https://files.example.com/geometry.png",
                "child_raw_reason_text": "我漏画了一条辅助线",
                "primary_error_type": "细节问题",
                "secondary_error_summary": "辅助线少画了一条",
            },
        )
        self.assertEqual(upload.status_code, 201)

        response = self.client.get(
            f"/api/wechat/children/{self.student['id']}/wrong-question-library",
            headers=self.service_headers(),
            query_string={"open_id": "openid-1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["pdf_url"], f"/api/wechat/student-libraries/{self.student['id']}")
        self.assertEqual(payload["total_items"], 1)

    def test_parent_child_library_returns_404_for_different_parent_open_id(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-2", "nickname_snapshot": "Bob 妈妈"},
        )

        response = self.client.get(
            f"/api/wechat/children/{self.student['id']}/wrong-questions",
            headers=self.service_headers(),
            query_string={"open_id": "openid-2"},
        )

        self.assertEqual(response.status_code, 404)

    def test_parent_child_library_returns_404_for_unbound_student(self):
        unbound_student = lesson_manager.create_student_for_class(self.class_id, "Bob")
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(bind.status_code, 200)

        response = self.client.get(
            f"/api/wechat/children/{unbound_student['id']}/wrong-questions",
            headers=self.service_headers(),
            query_string={"open_id": "openid-1"},
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_invite_code_returns_404_with_error_message(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )

        response = self.client.post(
            "/api/wechat/bind-class",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "invite_code": "INVALID0"},
        )

        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertIn("error", payload)

if __name__ == "__main__":
    unittest.main()
