from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_processor
import config_runtime
import lesson_manager
import pdf_engine


class WrongQuestionPracticePackStorageTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("七年级 5 班", subject="数学", grade="七年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "王睿博")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_get_and_find_active_pack_job(self):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="reason",
            target="去分母漏乘",
            volume="standard",
        )

        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["mode"], "reason")
        self.assertEqual(job["target"], "去分母漏乘")
        self.assertEqual(job["volume"], "standard")
        self.assertEqual(job["requested_question_count"], 10)

        loaded = lesson_manager.get_wrong_question_practice_pack_job(job["id"])
        self.assertEqual(loaded["id"], job["id"])

        active = lesson_manager.find_active_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="reason",
            target="去分母漏乘",
            volume="standard",
        )
        self.assertEqual(active["id"], job["id"])

    def test_pack_job_student_rows_are_serialized(self):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="topic",
            target="几何",
            volume="light",
        )
        saved = lesson_manager.upsert_wrong_question_practice_pack_job_student(
            job_id=job["id"],
            student_id=self.student["id"],
            student_name_snapshot="王睿博",
            status="ready",
            requested_question_count=5,
            real_question_count=3,
            variant_question_count=2,
            pdf_path="/tmp/wang.pdf",
            generation_error="",
        )

        loaded = lesson_manager.get_wrong_question_practice_pack_job(job["id"])
        self.assertEqual(saved["status"], "ready")
        self.assertEqual(len(loaded["students"]), 1)
        self.assertEqual(loaded["students"][0]["student_name_snapshot"], "王睿博")
        self.assertEqual(loaded["students"][0]["real_question_count"], 3)
        self.assertEqual(loaded["students"][0]["variant_question_count"], 2)

    def test_mark_pack_job_status_and_zip_path(self):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="topic",
            target="计算",
            volume="intensive",
        )
        updated = lesson_manager.mark_wrong_question_practice_pack_job_status(
            job["id"],
            status="ready",
            zip_path="/tmp/class.zip",
            generation_error="",
        )

        self.assertEqual(updated["status"], "ready")
        self.assertEqual(updated["zip_path"], "/tmp/class.zip")
        self.assertEqual(updated["requested_question_count"], 15)

    def test_delete_user_removes_created_pack_job(self):
        request = lesson_manager.create_registration_request(
            "pack_creator",
            "练习包老师",
            "password123",
            recovery_phone="13800000001",
        )
        creator = lesson_manager.approve_registration_request(request["id"], self.owner["id"])
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=creator["id"],
            mode="topic",
            target="计算",
            volume="light",
        )

        lesson_manager.delete_user_for_actor(self.owner, creator["id"])

        self.assertIsNone(lesson_manager.get_user_by_username("pack_creator"))
        self.assertIsNone(lesson_manager.get_wrong_question_practice_pack_job(job["id"]))

    def test_delete_organization_removes_pack_job_student_rows(self):
        request = lesson_manager.create_organization_request(
            "错题包测试机构",
            "pack_org_owner",
            "练习包负责人",
            "password123",
            recovery_phone="13800000002",
        )
        other_owner, _invite = lesson_manager.approve_organization_request(request["id"], self.owner["id"])
        other_class_id = lesson_manager.save_class(
            "八年级 1 班",
            subject="数学",
            grade="八年级",
            organization_id=other_owner["organization_id"],
        )
        other_student = lesson_manager.create_student_for_class(other_class_id, "李明")
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=other_owner["organization_id"],
            class_id=other_class_id,
            created_by=other_owner["id"],
            mode="topic",
            target="几何",
            volume="light",
        )
        lesson_manager.upsert_wrong_question_practice_pack_job_student(
            job_id=job["id"],
            student_id=other_student["id"],
            student_name_snapshot="李明",
            status="ready",
            requested_question_count=5,
        )

        lesson_manager.delete_organization(other_owner["organization_id"])

        with lesson_manager.get_conn() as conn:
            org_row = conn.execute(
                "SELECT id FROM organizations WHERE id=?",
                (other_owner["organization_id"],),
            ).fetchone()
        self.assertIsNone(org_row)

    def test_create_pack_job_rejects_cross_organization_scope(self):
        request = lesson_manager.create_organization_request(
            "错题包隔离机构",
            "pack_scope_owner",
            "隔离负责人",
            "password123",
            recovery_phone="13800000003",
        )
        other_owner, _invite = lesson_manager.approve_organization_request(request["id"], self.owner["id"])
        other_class_id = lesson_manager.save_class(
            "九年级 2 班",
            subject="数学",
            grade="九年级",
            organization_id=other_owner["organization_id"],
        )

        with self.assertRaises(ValueError):
            lesson_manager.create_wrong_question_practice_pack_job(
                organization_id=self.owner["organization_id"],
                class_id=other_class_id,
                created_by=self.owner["id"],
                mode="topic",
                target="几何",
                volume="light",
            )
        with self.assertRaises(ValueError):
            lesson_manager.create_wrong_question_practice_pack_job(
                organization_id=other_owner["organization_id"],
                class_id=other_class_id,
                created_by=self.owner["id"],
                mode="topic",
                target="几何",
                volume="light",
            )

    def test_pack_job_student_upsert_rejects_cross_organization_student(self):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="topic",
            target="计算",
            volume="light",
        )
        request = lesson_manager.create_organization_request(
            "错题包学生隔离机构",
            "pack_student_scope_owner",
            "学生隔离负责人",
            "password123",
            recovery_phone="13800000004",
        )
        other_owner, _invite = lesson_manager.approve_organization_request(request["id"], self.owner["id"])
        other_class_id = lesson_manager.save_class(
            "六年级 3 班",
            subject="数学",
            grade="六年级",
            organization_id=other_owner["organization_id"],
        )
        other_student = lesson_manager.create_student_for_class(other_class_id, "赵敏")

        with self.assertRaises(ValueError):
            lesson_manager.upsert_wrong_question_practice_pack_job_student(
                job_id=job["id"],
                student_id=other_student["id"],
                student_name_snapshot="赵敏",
                status="ready",
                requested_question_count=5,
            )

        loaded = lesson_manager.get_wrong_question_practice_pack_job(job["id"])
        self.assertEqual(loaded["students"], [])


class WrongQuestionPracticePackCandidateTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("七年级 5 班", subject="数学", grade="七年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "王睿博")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-practice-pack-candidates")
        self.binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record(self, *, topic_category: str, primary_error_type: str, reason: str, question_text: str):
        return lesson_manager.create_wechat_wrong_question_submission(
            binding_id=self.binding["id"],
            image_url=f"https://files.example.com/{topic_category}-{primary_error_type}.png",
            child_raw_reason_text=reason,
            primary_error_type=primary_error_type,
            secondary_error_summary=reason,
            topic_category=topic_category,
            recognition_status="recognized",
            question_text=question_text,
        )

    def test_topic_mode_selects_historical_matching_records_without_current_week_limit(self):
        geometry = self._record(
            topic_category="几何",
            primary_error_type="方法问题",
            reason="辅助线入口没找准",
            question_text="如图，证明角相等。",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET created_at=? WHERE id=?",
                ("2026-03-01 10:00:00", geometry["id"]),
            )
        self._record(
            topic_category="计算",
            primary_error_type="细节问题",
            reason="符号漏写",
            question_text="计算 -2+5。",
        )

        candidates = lesson_manager.list_targeted_wrong_question_practice_candidates(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            mode="topic",
            target="几何",
            limit=10,
            reference_date="2026-05-20",
        )

        self.assertEqual([item["id"] for item in candidates], [geometry["id"]])

    def test_reason_mode_matches_specific_reason_and_does_not_cross_fill(self):
        denominator = self._record(
            topic_category="计算",
            primary_error_type="知识点问题",
            reason="解方程去分母时右边没有同乘",
            question_text="解方程 (x-1)/2=3。",
        )
        self._record(
            topic_category="计算",
            primary_error_type="审题问题",
            reason="题目问法看漏",
            question_text="求 x 的取值范围。",
        )

        candidates = lesson_manager.list_targeted_wrong_question_practice_candidates(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            mode="reason",
            target="去分母",
            limit=10,
        )

        self.assertEqual([item["id"] for item in candidates], [denominator["id"]])

    def test_recently_archived_record_is_excluded_from_candidates(self):
        recent = self._record(
            topic_category="几何",
            primary_error_type="方法问题",
            reason="辅助线入口没找准",
            question_text="如图，证明角相等。",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET created_at=?, archive_status='archived', archived_at=?
                WHERE id=?
                """,
                ("2026-03-01 10:00:00", "2026-05-15 10:00:00", recent["id"]),
            )

        candidates = lesson_manager.list_targeted_wrong_question_practice_candidates(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            mode="topic",
            target="几何",
            limit=10,
            reference_date="2026-05-20",
        )

        self.assertEqual(candidates, [])

    def test_old_archived_recurring_record_can_be_included(self):
        recurring = self._record(
            topic_category="几何",
            primary_error_type="细节问题",
            reason="符号漏写，步骤遗漏",
            question_text="如图，证明角相等。",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE wrong_question_submissions
                SET created_at=?, archive_status='archived', archived_at=?
                WHERE id=?
                """,
                ("2026-03-01 10:00:00", "2026-04-10 10:00:00", recurring["id"]),
            )

        candidates = lesson_manager.list_targeted_wrong_question_practice_candidates(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            mode="topic",
            target="几何",
            limit=10,
            reference_date="2026-05-20",
        )

        self.assertEqual([item["id"] for item in candidates], [recurring["id"]])

    def test_reason_mode_does_not_match_target_from_question_text_only(self):
        self._record(
            topic_category="计算",
            primary_error_type="审题问题",
            reason="题目问法看漏",
            question_text="解方程时需要去分母。",
        )

        candidates = lesson_manager.list_targeted_wrong_question_practice_candidates(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            mode="reason",
            target="去分母",
            limit=10,
            reference_date="2026-05-20",
        )

        self.assertEqual(candidates, [])

    def test_future_dated_record_is_excluded_by_reference_date(self):
        future = self._record(
            topic_category="几何",
            primary_error_type="方法问题",
            reason="辅助线入口没找准",
            question_text="如图，证明角相等。",
        )
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE wrong_question_submissions SET created_at=? WHERE id=?",
                ("2026-06-01 10:00:00", future["id"]),
            )

        candidates = lesson_manager.list_targeted_wrong_question_practice_candidates(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            student_id=self.student["id"],
            mode="topic",
            target="几何",
            limit=10,
            reference_date="2026-05-20",
        )

        self.assertEqual(candidates, [])

    def test_schedule_places_real_questions_before_variants_across_seven_days(self):
        items = [
            {"practice_item_id": "real-1", "item_type": "real"},
            {"practice_item_id": "real-2", "item_type": "real"},
            {"practice_item_id": "variant-1", "item_type": "variant"},
            {"practice_item_id": "variant-2", "item_type": "variant"},
            {"practice_item_id": "variant-3", "item_type": "variant"},
        ]

        schedule = lesson_manager.build_wrong_question_practice_pack_schedule(items, start_date="2026-05-20")

        self.assertEqual(len(schedule), 7)
        self.assertEqual(schedule[0]["date"], "2026-05-20")
        self.assertEqual(schedule[0]["items"][0]["practice_item_id"], "real-1")
        self.assertEqual(schedule[1]["items"][0]["practice_item_id"], "real-2")
        scheduled_ids = [
            item["practice_item_id"]
            for day in schedule
            for item in day["items"]
        ]
        self.assertEqual(scheduled_ids, ["real-1", "real-2", "variant-1", "variant-2", "variant-3"])

    def test_schedule_preserves_real_variant_input_adjacency(self):
        items = [
            {"practice_item_id": "real-1", "item_type": "real"},
            {"practice_item_id": "variant-1", "item_type": "variant"},
            {"practice_item_id": "real-2", "item_type": "real"},
            {"practice_item_id": "variant-2", "item_type": "variant"},
        ]

        schedule = lesson_manager.build_wrong_question_practice_pack_schedule(items, start_date="2026-05-20")

        scheduled_ids = [
            item["practice_item_id"]
            for day in schedule
            for item in day["items"]
        ]
        self.assertEqual(scheduled_ids, ["real-1", "variant-1", "real-2", "variant-2"])


class WrongQuestionPracticePackAiNormalizationTestCase(unittest.TestCase):
    def test_normalize_variant_payload_requires_target_fields(self):
        payload = {
            "items": [
                {
                    "variant_id": "variant-1",
                    "source_record_id": "wechat-a",
                    "question_text": "解方程：x/2 + 1 = 3。",
                    "training_goal": "去分母时等式两边每一项同乘。",
                    "answer": "x=4",
                    "key_steps": ["两边同乘2", "x+2=6", "x=4"],
                    "pitfall_reminder": "不要只乘含分母的一边。",
                    "difficulty": "基础",
                }
            ]
        }

        normalized = ai_processor._normalize_wrong_question_practice_pack_variants(
            payload,
            expected_count=1,
            target="去分母",
        )

        self.assertEqual(normalized[0]["variant_id"], "variant-1")
        self.assertEqual(normalized[0]["answer"], "x=4")
        self.assertEqual(normalized[0]["key_steps"], ["两边同乘2", "x+2=6", "x=4"])

    def test_normalize_variant_payload_accepts_meaningful_target_tokens(self):
        payload = {
            "items": [
                {
                    "variant_id": "variant-1",
                    "source_record_id": "wechat-a",
                    "question_text": "解方程：x/2 + 1 = 3。",
                    "training_goal": "去分母时等式两边每一项同乘。",
                    "answer": "x=4",
                    "key_steps": ["两边同乘2", "x+2=6", "x=4"],
                    "pitfall_reminder": "不要漏乘常数项。",
                    "difficulty": "基础",
                }
            ]
        }

        normalized = ai_processor._normalize_wrong_question_practice_pack_variants(
            payload,
            expected_count=1,
            target="去分母漏乘",
        )

        self.assertEqual(normalized[0]["training_goal"], "去分母时等式两边每一项同乘。")

    def test_normalize_variant_payload_rejects_unrelated_target_text(self):
        payload = {
            "items": [
                {
                    "variant_id": "variant-1",
                    "source_record_id": "wechat-a",
                    "question_text": "如图，证明三角形全等。",
                    "training_goal": "识别对应边和对应角。",
                    "answer": "可由 SAS 判定全等。",
                    "key_steps": ["找对应边", "找夹角", "使用 SAS"],
                    "pitfall_reminder": "不要把非夹角当作夹角。",
                    "difficulty": "基础",
                }
            ]
        }

        with self.assertRaises(ValueError):
            ai_processor._normalize_wrong_question_practice_pack_variants(
                payload,
                expected_count=1,
                target="去分母漏乘",
            )

    def test_normalize_variant_payload_rejects_generic_missed_condition_text(self):
        payload = {
            "items": [
                {
                    "variant_id": "variant-1",
                    "source_record_id": "wechat-a",
                    "question_text": "如图，证明三角形全等。",
                    "training_goal": "识别对应边和对应角。",
                    "answer": "可由 SAS 判定全等。",
                    "key_steps": ["找对应边", "找夹角", "使用 SAS"],
                    "pitfall_reminder": "不要漏乘已知条件。",
                    "difficulty": "基础",
                }
            ]
        }

        with self.assertRaises(ValueError):
            ai_processor._normalize_wrong_question_practice_pack_variants(
                payload,
                expected_count=1,
                target="去分母漏乘",
            )

    def test_normalize_variant_payload_ignores_key_step_labels_for_target(self):
        payload = {
            "items": [
                {
                    "variant_id": "variant-1",
                    "source_record_id": "wechat-a",
                    "question_text": "如图，证明三角形全等。",
                    "training_goal": "识别对应边和对应角。",
                    "answer": "可由 SAS 判定全等。",
                    "key_steps": ["步骤一：找对应边", "步骤二：找夹角"],
                    "pitfall_reminder": "不要把非夹角当作夹角。",
                    "difficulty": "基础",
                }
            ]
        }

        with self.assertRaises(ValueError):
            ai_processor._normalize_wrong_question_practice_pack_variants(
                payload,
                expected_count=1,
                target="步骤遗漏",
            )

    def test_variant_review_passed_reads_first_conclusion_line(self):
        self.assertTrue(ai_processor._wrong_question_practice_pack_variant_review_passed("结论：通过\n题目可解。"))
        self.assertFalse(ai_processor._wrong_question_practice_pack_variant_review_passed("结论：不通过\n答案不一致。"))


class WrongQuestionPracticePackPdfPayloadTestCase(unittest.TestCase):
    def test_browser_payload_keeps_daily_plan_and_answers(self):
        items = [
            {
                "practice_item_id": "real-1",
                "item_type": "real",
                "question_text_snapshot": "解方程 x+1=3。",
                "answer": "x=2",
                "key_steps": ["x=3-1", "x=2"],
                "pitfall_reminder": "移项后要变号。",
            }
        ]
        schedule = [{"day_index": 1, "date": "2026-05-20", "items": items}]

        payload_items = pdf_engine._build_browser_wrong_question_practice_items(items)
        self.assertEqual(payload_items[0]["practiceItemId"], "real-1")
        self.assertEqual(payload_items[0]["itemType"], "real")
        self.assertEqual(payload_items[0]["answer"], "x=2")
        self.assertEqual(payload_items[0]["keySteps"], ["x=3-1", "x=2"])
        self.assertEqual(payload_items[0]["pitfallReminder"], "移项后要变号。")

        payload_schedule = pdf_engine._build_browser_wrong_question_practice_schedule(schedule)
        self.assertEqual(payload_schedule[0]["dayIndex"], 1)
        self.assertEqual(payload_schedule[0]["date"], "2026-05-20")
        self.assertEqual(payload_schedule[0]["items"][0]["practiceItemId"], "real-1")

    def test_browser_payload_skips_malformed_schedule_days(self):
        payload_schedule = pdf_engine._build_browser_wrong_question_practice_schedule(
            [
                None,
                {"day_index": 2, "date": "2026-05-21", "items": []},
            ]
        )

        self.assertEqual(len(payload_schedule), 1)
        self.assertEqual(payload_schedule[0]["dayIndex"], 2)


class WrongQuestionPracticePackWorkerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()

        import app as app_module

        self.app = app_module
        self.app.PDF_DIR = self.base / "pdfs"
        self.owner = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class("七年级 5 班", subject="数学", grade="七年级")
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner["id"])
        self.student = lesson_manager.create_student_for_class(self.class_id, "王睿博")
        self.empty_student = lesson_manager.create_student_for_class(self.class_id, "李明")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-practice-pack-worker")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        self.record = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/denominator.png",
            child_raw_reason_text="去分母时漏乘常数项",
            primary_error_type="知识点问题",
            secondary_error_summary="去分母漏乘",
            topic_category="计算",
            recognition_status="recognized",
            question_text="解方程 (x-1)/2=3。",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @mock.patch("app.finalize_ai_charge")
    @mock.patch("app.ensure_feature_credits_available")
    @mock.patch("pdf_engine.generate_wrong_question_practice_sheet_pdf")
    @mock.patch("ai_processor.review_wrong_question_practice_pack_variant")
    @mock.patch("ai_processor.generate_wrong_question_practice_pack_variants")
    @mock.patch("ai_processor.generate_wrong_question_practice_sheet_material")
    def test_worker_generates_student_pdfs_and_class_zip(
        self,
        material_mock,
        variants_mock,
        review_mock,
        pdf_mock,
        ensure_credits_mock,
        finalize_charge_mock,
    ):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="reason",
            target="去分母",
            volume="light",
        )
        variants_mock.return_value = [
            {
                "variant_id": "variant-1",
                "source_record_id": self.record["id"],
                "question_text": "解方程 x/2+1=3。",
                "training_goal": "练习去分母每一项同乘。",
                "answer": "x=4",
                "key_steps": ["两边同乘2", "x+2=6", "x=4"],
                "pitfall_reminder": "不要漏乘常数项。",
            }
        ]
        review_mock.return_value = "结论：通过\n题目可解。"

        def material_side_effect(**kwargs):
            return {
                "title": "王睿博 一周错题练习",
                "items": [
                    {
                        "wrong_question_record_id": str(item.get("wrong_question_record_id") or ""),
                        "ai_hint": "先找等量关系。",
                        "reason_blank_prompt": "这题容易错在____。",
                        "improvement_summary_prompt": "下次先____。",
                    }
                    for item in kwargs["items"]
                ],
            }

        material_mock.side_effect = material_side_effect

        def pdf_side_effect(**kwargs):
            output_path = Path(kwargs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"%PDF-1.4\npractice pack\n")
            return str(output_path)

        pdf_mock.side_effect = pdf_side_effect

        self.app._run_wrong_question_practice_pack_job(job_id=job["id"], user=self.owner)

        loaded = lesson_manager.get_wrong_question_practice_pack_job(job["id"])
        self.assertEqual(loaded["status"], "partial_failed")
        self.assertTrue(Path(loaded["zip_path"]).exists())
        students_by_name = {student["student_name_snapshot"]: student for student in loaded["students"]}
        self.assertEqual(students_by_name["王睿博"]["status"], "ready")
        self.assertEqual(students_by_name["王睿博"]["real_question_count"], 1)
        self.assertEqual(students_by_name["王睿博"]["variant_question_count"], 1)
        self.assertIn("匹配题量不足", students_by_name["王睿博"]["generation_error"])
        self.assertEqual(students_by_name["李明"]["status"], "skipped")
        self.assertEqual(students_by_name["李明"]["generation_error"], "没有匹配方向的历史错题")

        variants_mock.assert_called_once()
        self.assertEqual(variants_mock.call_args.kwargs["requested_count"], 4)
        review_mock.assert_called_once()
        pdf_mock.assert_called_once()
        pdf_kwargs = pdf_mock.call_args.kwargs
        self.assertEqual(len(pdf_kwargs["schedule"]), 7)
        self.assertEqual(len(pdf_kwargs["answer_items"]), 2)
        self.assertEqual(pdf_kwargs["pack_meta"]["mode"], "reason")
        ensure_credits_mock.assert_not_called()
        finalize_charge_mock.assert_not_called()

        with zipfile.ZipFile(loaded["zip_path"]) as archive:
            names = archive.namelist()
            self.assertTrue(any(name.endswith(".pdf") for name in names))
            self.assertIn("打包说明.txt", names)
            note = archive.read("打包说明.txt").decode("utf-8")
        self.assertIn("李明：没有匹配方向的历史错题", note)

    @mock.patch("app.finalize_ai_charge")
    @mock.patch("app.ensure_feature_credits_available")
    @mock.patch("pdf_engine.generate_wrong_question_practice_sheet_pdf")
    @mock.patch("ai_processor.review_wrong_question_practice_pack_variant", return_value="结论：通过\n题目可解。")
    @mock.patch("ai_processor.generate_wrong_question_practice_pack_variants")
    @mock.patch("ai_processor.generate_wrong_question_practice_sheet_material")
    def test_worker_limits_ai_variants_to_requested_gap(
        self,
        material_mock,
        variants_mock,
        _review_mock,
        pdf_mock,
        _ensure_credits_mock,
        _finalize_charge_mock,
    ):
        job = lesson_manager.create_wrong_question_practice_pack_job(
            organization_id=self.owner["organization_id"],
            class_id=self.class_id,
            created_by=self.owner["id"],
            mode="reason",
            target="去分母",
            volume="light",
        )
        variants_mock.return_value = [
            {
                "variant_id": f"variant-{index}",
                "source_record_id": self.record["id"],
                "question_text": f"解方程 x/{index + 1}+1=3。",
                "training_goal": "练习去分母每一项同乘。",
                "answer": "x=4",
                "key_steps": ["两边同乘"],
                "pitfall_reminder": "不要漏乘常数项。",
            }
            for index in range(8)
        ]
        material_mock.side_effect = lambda **kwargs: {
            "title": "王睿博 一周错题练习",
            "items": [
                {
                    "wrong_question_record_id": str(item.get("wrong_question_record_id") or ""),
                    "ai_hint": "",
                    "reason_blank_prompt": "",
                    "improvement_summary_prompt": "",
                }
                for item in kwargs["items"]
            ],
        }

        def pdf_side_effect(**kwargs):
            output_path = Path(kwargs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"%PDF-1.4\npractice pack\n")
            return str(output_path)

        pdf_mock.side_effect = pdf_side_effect

        self.app._run_wrong_question_practice_pack_job(job_id=job["id"], user=self.owner)

        loaded = lesson_manager.get_wrong_question_practice_pack_job(job["id"])
        students_by_name = {student["student_name_snapshot"]: student for student in loaded["students"]}
        self.assertEqual(students_by_name["王睿博"]["variant_question_count"], 4)
        pdf_kwargs = pdf_mock.call_args.kwargs
        self.assertEqual(len(pdf_kwargs["items"]), 5)
        self.assertEqual(len(pdf_kwargs["answer_items"]), 5)
        scheduled_ids = [
            item["practice_item_id"]
            for day in pdf_kwargs["schedule"]
            for item in day["items"]
        ]
        self.assertEqual(len(scheduled_ids), 5)
