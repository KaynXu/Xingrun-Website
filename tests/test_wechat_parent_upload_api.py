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

        self._credit_patchers = [
            patch("app.ensure_feature_credits_available"),
            patch("app.finalize_ai_charge"),
        ]
        for patcher in self._credit_patchers:
            patcher.start()

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
        for patcher in getattr(self, "_credit_patchers", []):
            patcher.stop()
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

        with patch("app.enqueue_wechat_wrong_question_upload_task") as enqueue_mock:
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

        self.assertEqual(upload.status_code, 202)
        task = upload.get_json()["task"]
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["binding_id"], binding["id"])
        self.assertEqual(task["student_id"], self.student["id"])
        self.assertEqual(task["image_url"], "https://files.example.com/record.png")
        self.assertEqual(upload.get_json()["student_library_pdf_url"], f"/api/wechat/student-libraries/{self.student['id']}")
        enqueue_mock.assert_called_once_with(task["id"])
        self.assertEqual(lesson_manager.list_wechat_wrong_question_submissions(), [])

    def test_worker_processes_pending_wrong_question_upload_task(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=binding["id"],
            image_url="https://files.example.com/record.png",
            child_raw_reason_text="我把乘法和加法一起从左往右算了",
        )

        from wrong_question_upload_worker import process_wechat_wrong_question_upload_task

        with patch("wrong_question_upload_worker.ai_processor.recognize_wrong_question_image", return_value=self.recognized_payload()), \
             patch(
                 "wrong_question_upload_worker.ai_processor.classify_wrong_question_reason",
                 return_value={
                     "display_text": "方法问题｜先算了加法，忽略乘法优先",
                     "primary_error_type": "方法问题",
                     "secondary_error_summary": "先算了加法，忽略乘法优先",
                 },
             ), \
             patch("wrong_question_upload_worker._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf"):
            result = process_wechat_wrong_question_upload_task(task["id"])

        self.assertEqual(result["status"], "ready")
        refreshed = lesson_manager.get_wechat_wrong_question_upload_task(task["id"])
        self.assertEqual(refreshed["status"], "ready")
        record = lesson_manager.get_wechat_wrong_question_submission(refreshed["record_id"])
        self.assertEqual(record["source"], "wechat_mp")
        self.assertEqual(record["teacher_user_id"], self.owner_id)
        self.assertEqual(record["class_id"], self.class_id)
        self.assertEqual(record["student_id"], self.student["id"])
        self.assertEqual(record["recognition_status"], "recognized")
        self.assertEqual(record["child_raw_reason_text"], "方法问题｜先算了加法，忽略乘法优先")
        self.assertEqual(record["primary_error_type"], "方法问题")
        self.assertEqual(record["secondary_error_summary"], "先算了加法，忽略乘法优先")
        self.assertEqual(record["student_library_pdf_path"], "/tmp/student-1.pdf")

    def test_worker_processes_image_only_wrong_question_upload_task(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=binding["id"],
            image_url="https://files.example.com/record.png",
            child_raw_reason_text="",
        )

        from wrong_question_upload_worker import process_wechat_wrong_question_upload_task

        with patch("wrong_question_upload_worker.ai_processor.recognize_wrong_question_image", return_value=self.recognized_payload()), \
             patch("wrong_question_upload_worker.ai_processor.classify_wrong_question_reason") as classify_mock, \
             patch("wrong_question_upload_worker._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf"):
            result = process_wechat_wrong_question_upload_task(task["id"])

        self.assertEqual(result["status"], "ready")
        refreshed = lesson_manager.get_wechat_wrong_question_upload_task(task["id"])
        record = lesson_manager.get_wechat_wrong_question_submission(refreshed["record_id"])
        self.assertEqual(record["child_raw_reason_text"], "待补充｜孩子暂未填写错因")
        self.assertEqual(record["primary_error_type"], "待补充")
        self.assertEqual(record["secondary_error_summary"], "孩子暂未填写错因")
        classify_mock.assert_not_called()

    def test_worker_marks_wrong_question_upload_task_failed(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=binding["id"],
            image_url="https://files.example.com/record.png",
            child_raw_reason_text="我没看懂题",
        )

        from wrong_question_upload_worker import process_wechat_wrong_question_upload_task

        with patch("wrong_question_upload_worker.ai_processor.recognize_wrong_question_image", side_effect=ValueError("题目识别失败")):
            result = process_wechat_wrong_question_upload_task(task["id"])

        self.assertEqual(result["status"], "failed")
        refreshed = lesson_manager.get_wechat_wrong_question_upload_task(task["id"])
        self.assertEqual(refreshed["status"], "failed")
        self.assertEqual(refreshed["error_message"], "题目识别失败")
        self.assertEqual(lesson_manager.list_wechat_wrong_question_submissions(), [])

    def test_wechat_service_can_fetch_parent_scoped_upload_task(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=binding["id"],
            image_url="https://files.example.com/record.png",
            child_raw_reason_text="我看漏了题目条件",
        )

        response = self.client.get(
            f"/api/wechat/wrong-question-upload-tasks/{task['id']}",
            headers=self.service_headers(),
            query_string={"open_id": "openid-1"},
        )
        forbidden = self.client.get(
            f"/api/wechat/wrong-question-upload-tasks/{task['id']}",
            headers=self.service_headers(),
            query_string={"open_id": "openid-2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["task"]["id"], task["id"])
        self.assertEqual(response.get_json()["task"]["status"], "pending")
        self.assertEqual(forbidden.status_code, 404)

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

    def test_wechat_service_upload_can_queue_image_only_task(self):
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

        with patch("app.enqueue_wechat_wrong_question_upload_task") as enqueue_mock:
            upload = self.client.post(
                "/api/wechat/wrong-questions",
                headers=self.service_headers(),
                json={
                    "open_id": "openid-1",
                    "binding_id": binding["id"],
                    "image_url": "https://files.example.com/record.png",
                },
            )

        self.assertEqual(upload.status_code, 202)
        task = upload.get_json()["task"]
        self.assertEqual(task["child_raw_reason_text"], "")
        self.assertEqual(task["child_reason_audio_url"], "")
        enqueue_mock.assert_called_once_with(task["id"])

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

        with patch("app.ai_processor.classify_wrong_question_reason") as classify_mock, \
             patch("app.enqueue_wechat_wrong_question_upload_task") as enqueue_mock:
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

        self.assertEqual(upload.status_code, 202)
        task = upload.get_json()["task"]
        self.assertEqual(task["child_raw_reason_text"], "我看漏了题目里要先把米换成厘米")
        self.assertEqual(task["child_reason_input_mode"], "voice")
        enqueue_mock.assert_called_once_with(task["id"])
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

        first_record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=first_binding["id"],
            image_url="https://files.example.com/record-1.png",
            child_raw_reason_text="我把乘法放到最后算了",
            primary_error_type="方法问题",
            secondary_error_summary="运算顺序放错了位置",
            recognition_status="recognized",
            question_text="计算 $2+3\\times4$ 的结果。",
            student_library_pdf_path="/tmp/student-1.pdf",
        )
        lesson_manager.create_wechat_wrong_question_submission(
            binding_id=second_binding["id"],
            image_url="https://files.example.com/record-2.png",
            child_raw_reason_text="我没看明白题目让求什么",
            primary_error_type="审题问题",
            secondary_error_summary="没看清题目到底要求什么",
            recognition_status="recognized",
            question_text="计算 $4+5$ 的结果。",
            student_library_pdf_path="/tmp/student-2.pdf",
        )

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
        self.assertEqual(payload["items"][0]["id"], first_record["id"])

    def test_wechat_upload_returns_task_before_non_geometry_recognition(self):
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

        with patch("app.enqueue_wechat_wrong_question_upload_task") as enqueue_mock:
            response = self.client.post(
                "/api/wechat/wrong-questions",
                headers=self.service_headers(),
                json={
                    "open_id": "openid-1",
                    "binding_id": binding["id"],
                    "image_url": "https://files.example.com/record.png",
                    "child_raw_reason_text": "我把乘法放到最后算了",
                },
            )

        self.assertEqual(response.status_code, 202)
        task = response.get_json()["task"]
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["record_id"], "")
        self.assertEqual(response.get_json()["student_library_pdf_url"], f"/api/wechat/student-libraries/{self.student['id']}")
        enqueue_mock.assert_called_once_with(task["id"])

    def test_worker_records_failed_non_geometry_recognition(self):
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        task = lesson_manager.create_wechat_wrong_question_upload_task(
            binding_id=binding["id"],
            image_url="https://files.example.com/record.png",
            child_raw_reason_text="我把乘法放到最后算了",
        )

        from wrong_question_upload_worker import process_wechat_wrong_question_upload_task

        with patch("wrong_question_upload_worker.ai_processor.recognize_wrong_question_image", side_effect=ValueError("题目识别失败，请重新识别")):
            result = process_wechat_wrong_question_upload_task(task["id"])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_message"], "题目识别失败，请重新识别")
        self.assertEqual(lesson_manager.list_wechat_wrong_question_submissions(), [])

    def test_wechat_child_library_endpoint_returns_shared_pdf_url(self):
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
        lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/geometry.png",
            child_raw_reason_text="我漏画了一条辅助线",
            primary_error_type="细节问题",
            secondary_error_summary="辅助线少画了一条",
            recognition_status="recognized",
            is_geometry=True,
            student_library_pdf_path="/tmp/student-1.pdf",
        )

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

    def test_bound_parent_can_see_same_child_wrong_questions_uploaded_by_other_parent(self):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-mother", "nickname_snapshot": "Alice 妈妈"},
        )
        mother_bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-mother",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(mother_bind.status_code, 200)
        mother_binding = mother_bind.get_json()["binding"]
        record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=mother_binding["id"],
            image_url="https://files.example.com/mother-upload.png",
            child_raw_reason_text="我把单位换算漏掉了",
            recognition_status="recognized",
        )

        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-father", "nickname_snapshot": "Alice 爸爸"},
        )
        father_bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={
                "open_id": "openid-father",
                "class_id": self.class_id,
                "student_id": self.student["id"],
            },
        )
        self.assertEqual(father_bind.status_code, 200)

        response = self.client.get(
            f"/api/wechat/children/{self.student['id']}/wrong-questions",
            headers=self.service_headers(),
            query_string={"open_id": "openid-father"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item["id"] for item in payload["items"]], [record["id"]])
        self.assertEqual(payload["total"], 1)

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
