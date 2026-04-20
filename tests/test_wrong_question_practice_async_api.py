import gc
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module
import config_runtime
import lesson_manager


class WrongQuestionPracticeAsyncApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("六年级 9 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-practice-async")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        self.record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/practice-worker.png",
            child_raw_reason_text="我把乘法顺序放错了",
            primary_error_type="细节问题",
            secondary_error_summary="运算顺序判断不稳定",
            recognition_status="recognized",
            is_geometry=False,
            question_text="计算 $2+3\\times4$ 的结果。",
            question_text_source="teacher",
        )
        self.sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=self.owner["id"],
            selected_records=[lesson_manager.get_wechat_wrong_question_submission(self.record["id"])],
        )

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    @patch("app.finalize_ai_charge")
    @patch("app.ensure_feature_credits_available")
    @patch("pdf_engine.generate_wrong_question_practice_sheet_pdf", return_value="/tmp/practice-sheet.pdf")
    @patch("ai_processor.generate_wrong_question_practice_sheet_material")
    def test_worker_generates_pdf_and_marks_sheet_ready(
        self,
        mock_generate_material,
        mock_generate_pdf,
        _mock_credits,
        mock_finalize,
    ):
        mock_generate_material.return_value = {
            "title": "Alice 错题练习",
            "items": [
                {
                    "wrong_question_record_id": self.record["id"],
                    "ai_hint": "先回忆乘法和加法的先后顺序，再看自己是不是少检查了一步。",
                    "reason_blank_prompt": "这题我错在 ______，因为我忽略了 ______。",
                    "improvement_summary_prompt": "以后遇到同类题，我会先 ______，再 ______，避免 ______。",
                }
            ],
        }

        app_module._run_wrong_question_practice_generation_job(
            sheet_id=self.sheet["id"],
            user={"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
        )

        saved = lesson_manager.get_wrong_question_practice_sheet(self.sheet["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "ready")
        self.assertEqual(saved["pdf_path"], "/tmp/practice-sheet.pdf")
        self.assertEqual(saved["generation_error"], "")
        self.assertEqual(saved["items"][0]["ai_hint"], "先回忆乘法和加法的先后顺序，再看自己是不是少检查了一步。")
        mock_generate_material.assert_called_once()
        material_kwargs = mock_generate_material.call_args.kwargs
        self.assertEqual(material_kwargs["student_name"], "Alice")
        self.assertEqual(material_kwargs["class_name"], "六年级 9 班")
        self.assertEqual(material_kwargs["teacher_name"], self.owner["display_name"])
        self.assertEqual(material_kwargs["items"][0]["wrong_question_record_id"], self.record["id"])
        self.assertEqual(material_kwargs["items"][0]["question_text_snapshot"], "计算 $2+3\\times4$ 的结果。")
        self.assertTrue(material_kwargs["include_usage"])
        mock_generate_pdf.assert_called_once()
        mock_finalize.assert_called_once()

    @patch("pdf_engine.generate_wrong_question_practice_sheet_pdf")
    @patch("ai_processor.generate_wrong_question_practice_sheet_material")
    def test_worker_skips_non_pending_sheet(
        self,
        mock_generate_material,
        mock_generate_pdf,
    ):
        lesson_manager.mark_wrong_question_practice_sheet_failed(self.sheet["id"], "旧错误")

        app_module._run_wrong_question_practice_generation_job(
            sheet_id=self.sheet["id"],
            user={"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
        )

        saved = lesson_manager.get_wrong_question_practice_sheet(self.sheet["id"])
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["generation_error"], "旧错误")
        mock_generate_material.assert_not_called()
        mock_generate_pdf.assert_not_called()

    @patch("app.ensure_feature_credits_available")
    @patch("ai_processor.generate_wrong_question_practice_sheet_material", side_effect=RuntimeError("boom"))
    def test_worker_writes_sanitized_ai_error_message(self, _mock_generate_material, _mock_credits):
        app_module._run_wrong_question_practice_generation_job(
            sheet_id=self.sheet["id"],
            user={"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
        )

        saved = lesson_manager.get_wrong_question_practice_sheet(self.sheet["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["generation_error"], "AI 生成失败，请稍后重试")

    @patch("app.ensure_feature_credits_available")
    @patch("pdf_engine.generate_wrong_question_practice_sheet_pdf", side_effect=RuntimeError("pdf boom"))
    @patch(
        "ai_processor.generate_wrong_question_practice_sheet_material",
    )
    def test_worker_writes_sanitized_pdf_error_message(
        self,
        mock_generate_material,
        _mock_generate_pdf,
        _mock_credits,
    ):
        mock_generate_material.return_value = {
            "title": "Alice 错题练习",
            "items": [
                {
                    "wrong_question_record_id": self.record["id"],
                    "ai_hint": "提示",
                    "reason_blank_prompt": "挖空",
                    "improvement_summary_prompt": "总结",
                }
            ],
        }
        app_module._run_wrong_question_practice_generation_job(
            sheet_id=self.sheet["id"],
            user={"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
        )

        saved = lesson_manager.get_wrong_question_practice_sheet(self.sheet["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["generation_error"], "PDF 生成失败，请稍后重试")


if __name__ == "__main__":
    unittest.main()
