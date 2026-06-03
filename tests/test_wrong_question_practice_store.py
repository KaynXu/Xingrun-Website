import json
import tempfile
import unittest
from pathlib import Path

import config_runtime
import lesson_manager


class WrongQuestionPracticeStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = base / "xingrun.db"
        config_runtime.CFG_PATH = base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()

        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("六年级 9 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-practice-store")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        self.binding_id = binding["id"]

        self.record_one = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding_id,
            image_url="https://files.example.com/non-geometry.png",
            child_raw_reason_text="我把乘法放到最后算了",
            primary_error_type="细节问题",
            secondary_error_summary="运算顺序判断不稳定",
            topic_category="四则混合运算",
            recognition_status="recognized",
            is_geometry=False,
            question_text="计算 $2+3\\times4$ 的结果。",
            question_text_source="teacher",
        )
        self.record_two = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding_id,
            image_url="https://files.example.com/geometry.png",
            child_raw_reason_text="我没有看清辅助线",
            primary_error_type="审题问题",
            secondary_error_summary="图形关系判断不完整",
            topic_category="几何辅助线",
            recognition_status="recognized",
            is_geometry=True,
            question_text="",
            question_text_source="ai",
            diagram_type="geometry",
            diagram_spec={
                "type": "geometry",
                "points": [{"label": "A", "x": 0, "y": 1}],
                "segments": [],
            },
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _selected_records_in_order(self, *record_ids: str) -> list[dict]:
        records = {
            item["id"]: item
            for item in lesson_manager.list_student_wrong_question_library_records(self.student["id"])
        }
        return [records[record_id] for record_id in record_ids]

    def test_create_pending_wrong_question_practice_sheet_persists_selected_snapshots(self):
        selected_records = self._selected_records_in_order(self.record_two["id"], self.record_one["id"])

        sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=self.owner["id"],
            selected_records=selected_records,
        )

        self.assertEqual(sheet["status"], "pending")
        self.assertEqual(sheet["question_count"], 2)
        self.assertEqual(sheet["student_id"], self.student["id"])

        saved = lesson_manager.get_wrong_question_practice_sheet(sheet["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "pending")
        self.assertEqual(saved["student_name_snapshot"], "Alice")
        self.assertEqual(saved["class_name_snapshot"], "六年级 9 班")
        self.assertEqual(saved["items"][0]["wrong_question_record_id"], self.record_two["id"])
        self.assertTrue(saved["items"][0]["is_geometry"])
        self.assertEqual(saved["items"][0]["cause_note_snapshot"], "图形关系判断不完整")
        self.assertEqual(saved["items"][0]["topic_category_snapshot"], "几何辅助线")
        self.assertEqual(saved["items"][0]["diagram_type_snapshot"], "geometry")
        self.assertEqual(
            json.loads(saved["items"][0]["diagram_spec_json_snapshot"])["points"][0]["label"],
            "A",
        )
        self.assertEqual(saved["items"][1]["wrong_question_record_id"], self.record_one["id"])
        self.assertEqual(saved["items"][1]["question_text_snapshot"], "计算 $2+3\\times4$ 的结果。")
        self.assertEqual(saved["items"][1]["child_reason_text_snapshot"], "我把乘法放到最后算了")
        self.assertEqual(saved["items"][1]["topic_category_snapshot"], "四则混合运算")

    def test_mark_wrong_question_practice_sheet_succeeded_saves_generated_prompts_and_pdf(self):
        sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=self.owner["id"],
            selected_records=self._selected_records_in_order(self.record_one["id"], self.record_two["id"]),
        )

        lesson_manager.mark_wrong_question_practice_sheet_succeeded(
            sheet["id"],
            generated_items=[
                {
                    "wrong_question_record_id": self.record_one["id"],
                    "ai_hint": "先回忆运算顺序，再检查自己是不是把乘法拖到了最后。",
                    "reason_blank_prompt": "这题我错在 ______，因为我忽略了 ______。",
                    "improvement_summary_prompt": "下次做这类题，我会先 ______，再 ______，避免 ______。",
                    "structured_content": {
                        "mistake_focus": "运算顺序漏检",
                        "review_goal": "先乘除后加减",
                        "method_hint_lines": ["先圈乘号，再决定第一步。"],
                        "blank_review_blocks": [
                            {
                                "title": "运算顺序补全",
                                "lines": ["这题我错在 ______，因为我忽略了 ______。"],
                            }
                        ],
                    },
                },
                {
                    "wrong_question_record_id": self.record_two["id"],
                    "ai_hint": "先标出已知线段和角，再回看辅助线是否真的服务于结论。",
                    "reason_blank_prompt": "这题我漏看了 ______，所以图形关系判断成了 ______。",
                    "improvement_summary_prompt": "以后碰到几何题，我会先 ______，再 ______，避免再次漏掉 ______。",
                },
            ],
            pdf_path="/tmp/wrong-question-practice-1.pdf",
        )

        saved = lesson_manager.get_wrong_question_practice_sheet(sheet["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "ready")
        self.assertEqual(saved["pdf_path"], "/tmp/wrong-question-practice-1.pdf")
        self.assertEqual(saved["generation_error"], "")
        self.assertEqual(
            saved["items"][0]["reason_blank_prompt"],
            "这题我错在 ______，因为我忽略了 ______。",
        )
        self.assertEqual(
            saved["items"][1]["improvement_summary_prompt"],
            "以后碰到几何题，我会先 ______，再 ______，避免再次漏掉 ______。",
        )
        self.assertEqual(saved["items"][0]["structured_content"]["mistake_focus"], "运算顺序漏检")
        self.assertEqual(
            saved["items"][0]["structured_content"]["blank_review_blocks"][0]["title"],
            "运算顺序补全",
        )
        self.assertEqual(saved["items"][1]["structured_content"], {})

    def test_mark_wrong_question_practice_sheet_failed_records_error(self):
        sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=self.owner["id"],
            selected_records=self._selected_records_in_order(self.record_one["id"]),
        )

        lesson_manager.mark_wrong_question_practice_sheet_failed(
            sheet["id"],
            "AI 生成失败，请稍后重试",
        )

        saved = lesson_manager.get_wrong_question_practice_sheet(sheet["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["generation_error"], "AI 生成失败，请稍后重试")
        self.assertEqual(saved["pdf_path"], "")

    def test_delete_wrong_question_practice_sheet_removes_sheet_and_items(self):
        sheet = lesson_manager.create_pending_wrong_question_practice_sheet(
            created_by=self.owner["id"],
            selected_records=self._selected_records_in_order(self.record_one["id"], self.record_two["id"]),
        )
        lesson_manager.mark_wrong_question_practice_sheet_succeeded(
            sheet["id"],
            generated_items=[
                {
                    "wrong_question_record_id": self.record_one["id"],
                    "ai_hint": "下次做这类题，先检查运算顺序。",
                    "reason_blank_prompt": "这题我错在 ______，因为我忽略了 ______。",
                    "improvement_summary_prompt": "以后遇到同类题，我会先 ______，做完再 ______。",
                },
                {
                    "wrong_question_record_id": self.record_two["id"],
                    "ai_hint": "下次做几何题，先把图形关系看完整。",
                    "reason_blank_prompt": "这题我漏看了 ______，所以判断成了 ______。",
                    "improvement_summary_prompt": "以后碰到几何题，我会先 ______，再 ______。",
                },
            ],
            pdf_path="/tmp/practice-delete.pdf",
        )

        deleted = lesson_manager.delete_wrong_question_practice_sheet(sheet["id"])

        self.assertIsNotNone(deleted)
        self.assertEqual(deleted["id"], sheet["id"])
        self.assertIsNone(lesson_manager.get_wrong_question_practice_sheet(sheet["id"]))
        self.assertEqual(lesson_manager.list_wrong_question_practice_sheets_for_student(self.student["id"]), [])
