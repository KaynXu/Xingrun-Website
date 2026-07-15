import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime
import lesson_manager


class ClassCommentaryMemoryStudentDeleteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        self.old_cfg = config_runtime.CFG_PATH
        self.old_enabled = os.environ.get("XR_CLASS_COMMENTARY_MEMORY_ENABLED")
        lesson_manager.DB_PATH = Path(self.tmp.name) / "test.db"
        config_runtime.CFG_PATH = Path(self.tmp.name) / "config.json"
        os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = "true"
        config_runtime.write_file_config({"class_commentary_memory_enabled": True})
        lesson_manager.init_db()
        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.app_module = importlib.import_module("app")

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        config_runtime.CFG_PATH = self.old_cfg
        if self.old_enabled is None:
            os.environ.pop("XR_CLASS_COMMENTARY_MEMORY_ENABLED", None)
        else:
            os.environ["XR_CLASS_COMMENTARY_MEMORY_ENABLED"] = self.old_enabled
        self.tmp.cleanup()

    def _create_student_memory(self, *, extract=True):
        class_id = lesson_manager.save_class(
            "Student memory delete test",
            subject="Math",
            grade="Grade 7",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        student = lesson_manager.create_student_for_class(class_id, "Student One")
        skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="student-memory-delete-test",
            actor_user_id=self.teacher["id"],
            source_path="/skills/student-memory-delete-test/SKILL.md",
            content="Start with progress, then give one next step.",
        )
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/student-memory-delete.m4a",
            audio_filename="student-memory-delete.m4a",
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            task["id"],
            "Student One needs to keep checking each answer.",
        )
        generation = lesson_manager.reserve_class_commentary_generation(
            task_id=task["id"],
            generation_request_id="student-memory-delete-generation",
            skill_registry_id=skill["registry_id"],
            attending_roster=[
                {"student_id": student["id"], "student_name": student["name"]}
            ],
            model_provider="deepseek",
            model_name="deepseek-chat",
            model_parameters={"temperature": 0.2},
            prompt_version="class-commentary-v1",
            prompt_payload={"messages": []},
            memory_context={"records": [], "rendered_text": ""},
        )
        lesson_manager.complete_class_commentary_generation(
            generation["id"],
            "Student One: Keep checking each answer.",
        )
        revision = lesson_manager.confirm_class_commentary_feedback(
            task_id=task["id"],
            generation_id=generation["id"],
            teacher_user_id=self.teacher["id"],
            feedback_text="Student One: Check every answer before moving on.",
            learn_requested=True,
            expected_draft_version=0,
            confirmation_request_id="student-memory-delete-confirmation",
        )
        job = lesson_manager.get_class_commentary_memory_extraction_job_for_revision(
            revision["id"]
        )
        if not extract:
            return class_id, student, {"revision": revision, "job": job}
        claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
            job["id"], claim_owner="student-delete-test"
        )
        extracted = lesson_manager.commit_class_commentary_memory_extraction(
            job["id"],
            claim_token=claimed["claim_token"],
            items=[
                {
                    "memory_type": "student_fact",
                    "student_id": student["id"],
                    "memory_text": "Needs to keep checking each answer",
                    "confidence": 0.9,
                }
            ],
        )
        return class_id, student, extracted

    def test_memory_reference_forces_archive_and_prepares_student_cleanup(self):
        _, student, extracted = self._create_student_memory()
        record_id = extracted["records"][0]["id"]
        evidence_id = extracted["evidence"][0]["id"]
        with lesson_manager.get_conn() as conn:
            conn.execute("DELETE FROM class_students WHERE student_id=?", (student["id"],))
            conn.execute(
                "DELETE FROM student_class_history WHERE student_id=?", (student["id"],)
            )

        result = lesson_manager.delete_or_archive_student_profile(
            student["id"], self.teacher["organization_id"]
        )

        self.assertEqual(result["action"], "archived")
        self.assertEqual(result["reference_count"], 1)
        self.assertEqual(result["memory_cleanup"]["scope_type"], "student")
        self.assertEqual(result["memory_cleanup"]["scope_id"], student["id"])
        self.assertEqual(result["memory_cleanup"]["record_ids"], [record_id])
        self.assertEqual(result["memory_cleanup"]["evidence_ids"], [evidence_id])
        self.assertEqual(
            lesson_manager.get_student_profile(student["id"])["status"], "archived"
        )
        record = lesson_manager.get_class_commentary_memory_records_by_ids([record_id])[0]
        operation = lesson_manager.get_class_commentary_memory_operation(
            result["memory_cleanup"]["operation_ids"][0]
        )
        self.assertEqual(record["desired_status"], "deleted")
        self.assertEqual(record["active_evidence_count"], 0)
        self.assertEqual(operation["source_type"], "cleanup")
        self.assertEqual(operation["cleanup_scope_type"], "student")
        self.assertEqual(operation["cleanup_scope_id"], student["id"])

    def test_delete_api_dispatches_student_cleanup_after_commit(self):
        _, student, extracted = self._create_student_memory()
        record_id = extracted["records"][0]["id"]
        evidence_id = extracted["evidence"][0]["id"]
        token = lesson_manager.create_auth_session(self.teacher["id"])
        client = self.app_module.app.test_client()
        observed = []

        def observe_committed_cleanup():
            with lesson_manager.get_conn() as conn:
                evidence = conn.execute(
                    "SELECT status FROM class_commentary_memory_evidence WHERE id=?",
                    (evidence_id,),
                ).fetchone()
                record = conn.execute(
                    "SELECT desired_status FROM class_commentary_memory_records WHERE id=?",
                    (record_id,),
                ).fetchone()
                operation_count = conn.execute(
                    """
                    SELECT COUNT(*) AS value
                    FROM class_commentary_memory_operations
                    WHERE source_type='cleanup'
                      AND cleanup_scope_type='student'
                      AND cleanup_scope_id=?
                    """,
                    (student["id"],),
                ).fetchone()["value"]
            observed.append(
                (evidence["status"], record["desired_status"], int(operation_count))
            )
            return {"enabled": True}

        with patch.object(
            self.app_module,
            "_dispatch_class_commentary_memory_best_effort",
            side_effect=observe_committed_cleanup,
        ) as dispatch:
            response = client.delete(
                f"/api/students/{student['id']}",
                headers={"X-Auth-Token": token},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["action"], "archived")
        self.assertNotIn("memory_cleanup", response.get_json())
        dispatch.assert_called_once_with()
        self.assertEqual(observed, [("revoked", "deleted", 1)])

    def test_claimed_job_cannot_relearn_after_student_is_archived(self):
        _, student, pending = self._create_student_memory(extract=False)
        job = pending["job"]
        claimed = lesson_manager.claim_class_commentary_memory_extraction_job(
            job["id"],
            claim_owner="delayed-student-memory-worker",
        )
        self.assertEqual(claimed["status"], "running")

        result = lesson_manager.delete_or_archive_student_profile(
            student["id"],
            self.teacher["organization_id"],
        )
        delayed = lesson_manager.commit_class_commentary_memory_extraction(
            job["id"],
            claim_token=claimed["claim_token"],
            items=[
                {
                    "memory_type": "student_fact",
                    "student_id": student["id"],
                    "memory_text": "This delayed fact must not be stored",
                    "confidence": 0.9,
                }
            ],
        )

        self.assertEqual(result["action"], "archived")
        self.assertEqual(
            result["memory_cleanup"]["obsolete_extraction_job_ids"],
            [job["id"]],
        )
        self.assertEqual(delayed["job"]["status"], "obsolete")
        self.assertEqual(delayed["records"], [])
        self.assertEqual(delayed["evidence"], [])
        with lesson_manager.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM class_commentary_memory_records"
                ).fetchone()[0],
                0,
            )


if __name__ == "__main__":
    unittest.main()
