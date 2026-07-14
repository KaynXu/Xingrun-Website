import copy
import hashlib
import json
import os
import tempfile
import unittest

import lesson_manager


class ClassCommentaryGenerationStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()

        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "课堂点评生成测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        first_student = lesson_manager.create_student_for_class(self.class_id, "小王")
        second_student = lesson_manager.create_student_for_class(self.class_id, "小李")
        self.roster = [
            {"student_id": first_student["id"], "student_name": first_student["name"]},
            {"student_id": second_student["id"], "student_name": second_student["name"]},
        ]
        self.transcript = "小王计算更稳了, 小李需要继续练习验算."
        self.task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/class-commentary-generation.m4a",
            audio_filename="class-commentary-generation.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            self.task["id"],
            self.transcript,
        )

        self.skill_content = "先写学生本次表现, 再给一条可执行建议."
        imported = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="generation-store-teacher",
            owner_teacher_user_id=self.teacher["id"],
            source_path="/skills/generation-store-teacher/SKILL.md",
            content=self.skill_content,
        )
        self.skill_registry_id = imported["registry_id"]
        self.skill_version_id = imported["active_version_id"]
        self.model_parameters = {"temperature": 0.2, "top_p": 0.9}
        self.prompt_payload = {
            "messages": [
                {"role": "system", "content": "按课堂点评规范生成反馈."},
                {"role": "user", "content": self.transcript},
            ],
            "response_format": "text",
        }
        self.memory_context = {
            "records": [
                {
                    "memory_id": "mem-1",
                    "scope": "student",
                    "student_id": first_student["id"],
                    "text": "上次建议加强验算.",
                }
            ],
            "rendered_text": "历史参考: 上次建议加强验算.",
        }

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    @staticmethod
    def _canonical_json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _hash_json(cls, value):
        return hashlib.sha256(cls._canonical_json(value).encode("utf-8")).hexdigest()

    def _reserve(self, request_id, attending_roster=None):
        return lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id=request_id,
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster if attending_roster is None else attending_roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=self.model_parameters,
            prompt_version="class-commentary-v1",
            prompt_payload=self.prompt_payload,
            memory_context=self.memory_context,
        )

    def test_reservation_freezes_complete_snapshots_and_moves_task_pointer(self):
        expected_roster = copy.deepcopy(self.roster)
        expected_prompt_payload = copy.deepcopy(self.prompt_payload)
        expected_memory_context = copy.deepcopy(self.memory_context)

        reserved = self._reserve("generation-request-1")
        task_after_reservation = lesson_manager.get_class_commentary_task(self.task["id"])

        self.assertEqual(reserved["generation_no"], 1)
        self.assertEqual(task_after_reservation["generation_seq"], 1)
        self.assertEqual(task_after_reservation["latest_generation_id"], reserved["id"])
        self.assertEqual(task_after_reservation["status"], "generating")

        self.roster[0]["student_name"] = "被调用方修改的姓名"
        self.prompt_payload["messages"][0]["content"] = "被调用方修改的 prompt"
        self.memory_context["rendered_text"] = "被调用方修改的 memory"
        lesson_manager.save_class_commentary_transcript(self.task["id"], "后来修改的转写")

        saved = lesson_manager.get_class_commentary_generation(reserved["id"])
        with lesson_manager.get_conn() as conn:
            row = dict(
                conn.execute(
                    "SELECT * FROM class_commentary_generations WHERE id=?",
                    (reserved["id"],),
                ).fetchone()
            )

        self.assertEqual(saved["id"], reserved["id"])
        self.assertEqual(row["organization_id"], self.teacher["organization_id"])
        self.assertEqual(row["teacher_user_id"], self.teacher["id"])
        self.assertEqual(row["class_id"], self.class_id)
        self.assertEqual(row["subject_key"], "math")
        self.assertEqual(row["confirmed_transcript_version"], 1)
        self.assertEqual(row["confirmed_transcript_snapshot"], self.transcript)
        self.assertEqual(
            row["confirmed_transcript_hash"],
            hashlib.sha256(self.transcript.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(row["attending_roster_snapshot_json"], self._canonical_json(expected_roster))
        self.assertEqual(row["attending_roster_hash"], self._hash_json(expected_roster))
        self.assertEqual(row["attending_roster_explicit"], 1)
        self.assertEqual(row["skill_registry_id"], self.skill_registry_id)
        self.assertEqual(row["skill_id"], "generation-store-teacher")
        self.assertEqual(row["skill_version_id"], self.skill_version_id)
        self.assertEqual(row["skill_content_snapshot"], self.skill_content)
        self.assertEqual(
            row["skill_content_hash"],
            hashlib.sha256(self.skill_content.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(row["model_provider"], "deepseek")
        self.assertEqual(row["model_name"], "deepseek-chat")
        self.assertEqual(row["model_parameters_json"], self._canonical_json(self.model_parameters))
        self.assertEqual(row["prompt_version"], "class-commentary-v1")
        self.assertEqual(row["prompt_payload_snapshot_json"], self._canonical_json(expected_prompt_payload))
        self.assertEqual(row["prompt_payload_hash"], self._hash_json(expected_prompt_payload))
        self.assertEqual(row["memory_context_snapshot_json"], self._canonical_json(expected_memory_context))
        self.assertEqual(row["memory_context_hash"], self._hash_json(expected_memory_context))
        self.assertRegex(row["generation_request_payload_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(row["origin"], "runtime")
        self.assertEqual(row["snapshot_completeness"], "complete")
        self.assertEqual(json.loads(row["missing_snapshot_fields_json"]), [])
        self.assertEqual(row["status"], "generating")
        self.assertEqual(row["generated_feedback_text"], "")

    def test_same_request_is_idempotent_and_changed_roster_conflicts(self):
        first = self._reserve("generation-request-idempotent")
        repeated = self._reserve(
            "generation-request-idempotent",
            attending_roster=copy.deepcopy(self.roster),
        )

        self.assertEqual(repeated["id"], first["id"])
        self.assertEqual(
            lesson_manager.get_class_commentary_generation(first["id"])["id"],
            first["id"],
        )
        with self.assertRaises(lesson_manager.ClassCommentaryGenerationRequestConflict):
            self._reserve(
                "generation-request-idempotent",
                attending_roster=[copy.deepcopy(self.roster[0])],
            )

        task = lesson_manager.get_class_commentary_task(self.task["id"])
        with lesson_manager.get_conn() as conn:
            generation_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                (self.task["id"],),
            ).fetchone()[0]
        self.assertEqual(generation_count, 1)
        self.assertEqual(task["generation_seq"], 1)
        self.assertEqual(task["latest_generation_id"], first["id"])

    def test_same_request_ignores_later_prompt_and_memory_results(self):
        original_prompt = copy.deepcopy(self.prompt_payload)
        original_memory = copy.deepcopy(self.memory_context)
        first = self._reserve("generation-request-frozen-base-input")

        self.prompt_payload["messages"][1]["content"] = "后来重新组装的 prompt"
        self.memory_context = {
            "records": [{"memory_id": "mem-later", "text": "后来检索到的记忆"}],
            "rendered_text": "后来检索到的记忆",
        }

        repeated = self._reserve("generation-request-frozen-base-input")

        self.assertEqual(repeated["id"], first["id"])
        self.assertTrue(repeated["is_idempotent"])
        saved = lesson_manager.get_class_commentary_generation(first["id"])
        self.assertEqual(
            json.loads(saved["prompt_payload_snapshot_json"]),
            original_prompt,
        )
        self.assertEqual(
            json.loads(saved["memory_context_snapshot_json"]),
            original_memory,
        )

    def test_pending_execution_snapshot_can_only_be_finalized_once_before_completion(self):
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=self.task["id"],
            generation_request_id="generation-request-pending-execution",
            skill_registry_id=self.skill_registry_id,
            attending_roster=self.roster,
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters=self.model_parameters,
            prompt_version="class-commentary-v1",
        )
        self.assertEqual(generation["execution_snapshot_status"], "pending")
        with self.assertRaisesRegex(ValueError, "not finalized"):
            lesson_manager.complete_class_commentary_generation(
                generation["id"],
                "不能提前完成",
            )

        finalized = lesson_manager.finalize_class_commentary_generation_execution_snapshot(
            generation["id"],
            prompt_payload=self.prompt_payload,
            memory_context=self.memory_context,
        )
        repeated = lesson_manager.finalize_class_commentary_generation_execution_snapshot(
            generation["id"],
            prompt_payload=copy.deepcopy(self.prompt_payload),
            memory_context=copy.deepcopy(self.memory_context),
        )

        self.assertEqual(finalized["execution_snapshot_status"], "ready")
        self.assertTrue(finalized["execution_snapshot_finalized_at"])
        self.assertEqual(repeated["id"], finalized["id"])
        with self.assertRaises(lesson_manager.ClassCommentaryGenerationRequestConflict):
            lesson_manager.finalize_class_commentary_generation_execution_snapshot(
                generation["id"],
                prompt_payload={"messages": []},
                memory_context=self.memory_context,
            )
        completed = lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "冻结后完成",
        )
        self.assertEqual(completed["status"], "succeeded")

    def test_same_request_returns_original_after_skill_and_roster_change(self):
        first = self._reserve("generation-request-later-scope-change")
        removed_student_id = self.roster[-1]["student_id"]
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE class_commentary_skills SET status='disabled' WHERE id=?",
                (self.skill_registry_id,),
            )
            conn.execute(
                "DELETE FROM class_students WHERE class_id=? AND student_id=?",
                (self.class_id, removed_student_id),
            )

        repeated = self._reserve(
            "generation-request-later-scope-change",
            attending_roster=copy.deepcopy(self.roster),
        )

        self.assertEqual(repeated["id"], first["id"])
        self.assertTrue(repeated["is_idempotent"])
        with lesson_manager.get_conn() as conn:
            generation_count = conn.execute(
                "SELECT COUNT(*) FROM class_commentary_generations WHERE task_id=?",
                (self.task["id"],),
            ).fetchone()[0]
        self.assertEqual(generation_count, 1)

    def test_terminal_updates_are_sealed_and_late_completion_keeps_latest_generation(self):
        first = self._reserve("generation-request-first")
        second = self._reserve("generation-request-second")

        lesson_manager.complete_class_commentary_generation(first["id"], "第一版反馈")
        first_completed = lesson_manager.get_class_commentary_generation(first["id"])
        task_after_late_completion = lesson_manager.get_class_commentary_task(self.task["id"])

        self.assertEqual(first_completed["status"], "succeeded")
        self.assertEqual(first_completed["generated_feedback_text"], "第一版反馈")
        self.assertTrue(first_completed["completed_at"])
        self.assertEqual(task_after_late_completion["generation_seq"], 2)
        self.assertEqual(task_after_late_completion["latest_generation_id"], second["id"])
        self.assertEqual(task_after_late_completion["status"], "generating")
        self.assertEqual(task_after_late_completion["feedback_text"], "")

        lesson_manager.complete_class_commentary_generation(first["id"], "不应覆盖的反馈")
        first_after_repeated_completion = lesson_manager.get_class_commentary_generation(first["id"])
        self.assertEqual(first_after_repeated_completion["generated_feedback_text"], "第一版反馈")
        self.assertEqual(first_after_repeated_completion["completed_at"], first_completed["completed_at"])

        lesson_manager.fail_class_commentary_generation(second["id"], "provider_timeout")
        failed = lesson_manager.get_class_commentary_generation(second["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_code"], "provider_timeout")
        self.assertEqual(failed["generated_feedback_text"], "")
        self.assertTrue(failed["completed_at"])

        lesson_manager.complete_class_commentary_generation(second["id"], "失败后不应写入")
        failed_after_completion_attempt = lesson_manager.get_class_commentary_generation(second["id"])
        task_after_completion_attempt = lesson_manager.get_class_commentary_task(self.task["id"])
        self.assertEqual(failed_after_completion_attempt["status"], "failed")
        self.assertEqual(failed_after_completion_attempt["error_code"], "provider_timeout")
        self.assertEqual(failed_after_completion_attempt["generated_feedback_text"], "")
        self.assertEqual(failed_after_completion_attempt["completed_at"], failed["completed_at"])
        self.assertEqual(task_after_completion_attempt["latest_generation_id"], second["id"])
        self.assertEqual(task_after_completion_attempt["status"], "failed")
        self.assertEqual(task_after_completion_attempt["generation_error"], "provider_timeout")

    def test_completion_after_transcript_change_does_not_update_task_cache(self):
        generation = self._reserve("generation-request-before-transcript-edit")
        edited_transcript = "小王计算更稳了, 新增要求是继续检查书写步骤."
        task_after_edit = lesson_manager.save_class_commentary_transcript(
            self.task["id"],
            edited_transcript,
        )

        completed = lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "基于旧转写生成的反馈",
        )
        task_after_completion = lesson_manager.get_class_commentary_task(self.task["id"])

        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["generated_feedback_text"], "基于旧转写生成的反馈")
        self.assertEqual(task_after_edit["confirmed_transcript_version"], 2)
        self.assertEqual(task_after_completion["confirmed_transcript_version"], 2)
        self.assertEqual(task_after_completion["confirmed_transcript_text"], edited_transcript)
        self.assertEqual(task_after_completion["status"], "transcribed")
        self.assertEqual(task_after_completion["feedback_text"], "")


if __name__ == "__main__":
    unittest.main()
