from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager


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
