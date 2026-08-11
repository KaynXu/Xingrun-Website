import json
import os
import tempfile
import unittest
from types import SimpleNamespace

import lesson_manager
from class_commentary import CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2
from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V1,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2,
)
from class_commentary_memory_retrieval import (
    ClassCommentaryStudentMemoryRetrievalError,
    retrieve_isolated_student_memory_context,
    validate_isolated_student_memory_context_snapshot,
)
from class_commentary_student_generation_jobs import (
    process_class_commentary_student_generation_run,
)
from class_commentary_student_memory_v2 import (
    build_isolated_student_chat_request,
    build_safe_class_context,
    build_student_current_evidence,
    canonical_hash,
    canonical_json,
    content_hash,
    validate_isolated_prompt_privacy,
)
from credit_manager import finalize_ai_charge


class EmptyMemoryService:
    enabled = True

    def __init__(self):
        self.settings = SimpleNamespace(
            context_char_limit=3000, style_limit=5, student_limit=5
        )
        self.calls = []

    def search_style(self, query, **scope):
        self.calls.append(("style", query, scope))
        return []

    def search_student(self, query, **scope):
        self.calls.append(("student", query, scope))
        return []


class ProviderHttpError(RuntimeError):
    def __init__(self, status_code):
        super().__init__(f"provider returned {status_code}")
        self.status_code = status_code


class ClassCommentaryStudentGenerationV2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = lesson_manager.DB_PATH
        lesson_manager.DB_PATH = os.path.join(self.tmp.name, "test.db")
        lesson_manager.init_db()
        self.teacher = lesson_manager.get_user_by_username("Kayn")
        self.class_id = lesson_manager.save_class(
            "五人隔离测试班",
            subject="数学",
            grade="七年级",
            organization_id=self.teacher["organization_id"],
            teacher_user_id=self.teacher["id"],
        )
        self.students = [
            lesson_manager.create_student_for_class(self.class_id, name)
            for name in ("甲同学", "乙同学", "丙同学", "丁同学", "戊同学")
        ]
        self.task = lesson_manager.create_class_commentary_task(
            organization_id=self.teacher["organization_id"],
            class_id=self.class_id,
            teacher_user_id=self.teacher["id"],
            audio_path="/tmp/student-memory-v2.m4a",
            audio_filename="student-memory-v2.m4a",
        )
        self.transcript = (
            "本节课学习一元一次方程。"
            "甲同学移项步骤清楚。"
            "乙同学合并同类项稳定。"
            "丙同学能主动验算。"
            "丁同学需要检查符号。"
            "戊同学能说明等式性质。"
            "甲同学和乙同学一起讨论了最后一题。"
            "佳同学的近音内容不能归入任何学生。"
        )
        lesson_manager.mark_class_commentary_transcription_succeeded(
            self.task["id"], self.transcript
        )
        self.skill = lesson_manager.import_class_commentary_skill_manifest(
            organization_id=self.teacher["organization_id"],
            skill_id="student-memory-v2-test",
            actor_user_id=self.teacher["id"],
            source_path="/skills/student-memory-v2-test/SKILL.md",
            content="先肯定本节课证据, 再给一条具体建议.",
        )
        lesson_manager.insert_credit_ledger_entry(
            organization_id=self.teacher["organization_id"],
            direction="credit",
            amount=1000,
            source_type="manual_adjustment",
            source_id="student-memory-v2-test",
            note="test credits",
            operator_user_id=self.teacher["id"],
        )

    def tearDown(self):
        lesson_manager.DB_PATH = self.old_db
        self.tmp.cleanup()

    def _reserve(self, request_id="student-memory-v2-generation", students=None, **overrides):
        roster_students = students if students is not None else self.students
        params = {
            "task_id": self.task["id"],
            "generation_request_id": request_id,
            "skill_registry_id": self.skill["registry_id"],
            "attending_roster": [
                {"student_id": item["id"], "student_name": item["name"]}
                for item in roster_students
            ],
            "model_provider": "openai",
            "model_name": "deterministic-fake",
            "model_parameters": {"temperature": 0.55},
            "prompt_version": CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
            "attending_roster_explicit": True,
            "structured_feedback_enabled": True,
            "student_history_memory_mode": (
                CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_ISOLATED_V2
            ),
        }
        params.update(overrides)
        return lesson_manager.reserve_class_commentary_generation(**params)

    @staticmethod
    def _success_response(student_id):
        return json.dumps(
            {
                "schema_version": "class_commentary.student_feedback.v1",
                "items": [
                    {
                        "student_id": student_id,
                        "feedback_text": "本节课有明确进步, 请继续完成课后验算.",
                    }
                ],
            },
            ensure_ascii=False,
        )

    def _usage_count(self, generation_id):
        with lesson_manager.get_conn() as conn:
            return int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM ai_usage_ledger
                    WHERE source_record_type='class_commentary_student_generation_run'
                      AND source_record_id IN (
                          SELECT CAST(id AS TEXT)
                          FROM class_commentary_student_generation_runs
                          WHERE generation_id=?
                      )
                    """,
                    (generation_id,),
                ).fetchone()[0]
            )

    def test_five_students_use_independent_requests_and_publish_in_frozen_order(self):
        generation = self._reserve()
        runs = lesson_manager.list_class_commentary_student_generation_runs(
            generation["id"]
        )
        calls = []

        def generator(**kwargs):
            student_id = int(kwargs["students"][0]["id"])
            calls.append(
                {
                    "student_id": student_id,
                    "request_id": kwargs["request_id"],
                    "chat_request": kwargs["chat_request"],
                }
            )
            return self._success_response(student_id), {
                "provider": "openai",
                "model": "deterministic-fake",
                "input_tokens": 100,
                "output_tokens": 50,
            }

        service = EmptyMemoryService()
        for run in runs:
            result = process_class_commentary_student_generation_run(
                run["id"],
                runtime_config={"class_commentary_student_generation_timeout": 30},
                memory_service=service,
                generator=generator,
                claim_owner="five-student-proof",
            )
            self.assertEqual(result["status"], "succeeded")

        saved = lesson_manager.get_class_commentary_generation(generation["id"])
        payload = json.loads(saved["structured_feedback_json"])
        expected_ids = [item["id"] for item in self.students]
        self.assertEqual(saved["status"], "succeeded")
        self.assertEqual([item["student_id"] for item in payload["items"]], expected_ids)
        self.assertEqual([call["student_id"] for call in calls], expected_ids)
        self.assertEqual(len({call["request_id"] for call in calls}), 5)
        self.assertEqual(self._usage_count(generation["id"]), 5)
        self.assertEqual(
            [call[0] for call in service.calls],
            [value for _ in self.students for value in ("style", "student")],
        )

        for call in calls:
            serialized = canonical_json(call["chat_request"])
            visible_prompt = call["chat_request"]["messages"][1]["content"]
            target = next(
                item for item in self.students if item["id"] == call["student_id"]
            )
            self.assertIn(target["name"], serialized)
            self.assertIn(f'"student_id":{target["id"]}', visible_prompt)
            for other in self.students:
                if other["id"] == target["id"]:
                    continue
                self.assertNotIn(other["name"], serialized)
                self.assertNotIn(f'"student_id":{other["id"]}', visible_prompt)
            self.assertIn("[CURRENT_STUDENT]", serialized)
            self.assertIn("[CURRENT_CLASS_CONTEXT]", serialized)
            self.assertIn("[CURRENT_STUDENT_EVIDENCE]", serialized)
            self.assertIn("[STUDENT_HISTORY_MEMORIES]", serialized)
            self.assertIn("[TEACHER_STYLE_MEMORIES]", serialized)
            self.assertIn("[OUTPUT_RULES]", serialized)

        repeated = process_class_commentary_student_generation_run(
            runs[0]["id"],
            memory_service=service,
            generator=generator,
            claim_owner="must-not-repeat",
        )
        self.assertEqual(repeated["status"], "not_claimed")
        self.assertEqual(len(calls), 5)
        self.assertEqual(self._usage_count(generation["id"]), 5)

    def test_partial_failure_is_not_published_and_retry_skips_successful_runs(self):
        generation = self._reserve("partial-failure")
        runs = lesson_manager.list_class_commentary_student_generation_runs(
            generation["id"]
        )
        failed_student_id = self.students[2]["id"]
        calls = []

        def first_generator(**kwargs):
            student_id = int(kwargs["students"][0]["id"])
            calls.append((student_id, kwargs["request_id"]))
            if student_id == failed_student_id:
                raise ProviderHttpError(400)
            return self._success_response(student_id), {
                "provider": "openai",
                "model": "deterministic-fake",
                "input_tokens": 40,
                "output_tokens": 20,
            }

        service = EmptyMemoryService()
        for run in runs:
            process_class_commentary_student_generation_run(
                run["id"],
                memory_service=service,
                generator=first_generator,
                claim_owner="partial-failure",
            )

        failed_parent = lesson_manager.get_class_commentary_generation(generation["id"])
        self.assertEqual(failed_parent["status"], "failed")
        self.assertEqual(failed_parent["structured_feedback_json"], "")
        self.assertEqual(self._usage_count(generation["id"]), 4)

        retried = lesson_manager.retry_class_commentary_student_generation_runs(
            generation["id"],
            actor_user_id=self.teacher["id"],
            retry_request_id="partial-failure-retry",
        )
        self.assertEqual(retried["retried_student_ids"], [failed_student_id])
        retry_run = next(
            run
            for run in lesson_manager.list_class_commentary_student_generation_runs(
                generation["id"]
            )
            if run["student_id"] == failed_student_id
        )

        def retry_generator(**kwargs):
            student_id = int(kwargs["students"][0]["id"])
            calls.append((student_id, kwargs["request_id"]))
            return self._success_response(student_id), {
                "provider": "openai",
                "model": "deterministic-fake",
                "input_tokens": 40,
                "output_tokens": 20,
            }

        process_class_commentary_student_generation_run(
            retry_run["id"],
            memory_service=service,
            generator=retry_generator,
            claim_owner="partial-failure-retry",
        )
        completed = lesson_manager.get_class_commentary_generation(generation["id"])
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(self._usage_count(generation["id"]), 5)
        call_counts = {
            student["id"]: sum(call[0] == student["id"] for call in calls)
            for student in self.students
        }
        self.assertEqual(call_counts[failed_student_id], 2)
        self.assertTrue(
            all(
                count == 1
                for student_id, count in call_counts.items()
                if student_id != failed_student_id
            )
        )
        failed_request_ids = [
            request_id for student_id, request_id in calls if student_id == failed_student_id
        ]
        self.assertEqual(len(set(failed_request_ids)), 1)

    def test_charge_retry_reuses_response_and_does_not_duplicate_provider_or_debit(self):
        generation = self._reserve("charge-retry", students=[self.students[0]])
        run = lesson_manager.list_class_commentary_student_generation_runs(
            generation["id"]
        )[0]
        provider_calls = []
        charge_calls = []

        def generator(**kwargs):
            provider_calls.append(kwargs["request_id"])
            return self._success_response(run["student_id"]), {
                "provider": "openai",
                "model": "deterministic-fake",
                "input_tokens": 60,
                "output_tokens": 30,
            }

        def flaky_charge(**kwargs):
            charged = finalize_ai_charge(**kwargs)
            charge_calls.append((kwargs["request_id"], kwargs["request_payload_hash"]))
            if len(charge_calls) == 1:
                raise RuntimeError("crash after durable debit")
            return charged

        first = process_class_commentary_student_generation_run(
            run["id"],
            memory_service=EmptyMemoryService(),
            generator=generator,
            charge_finalizer=flaky_charge,
            claim_owner="charge-crash",
        )
        self.assertEqual(first["status"], "response_received")
        self.assertEqual(len(provider_calls), 1)
        self.assertEqual(self._usage_count(generation["id"]), 1)
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_student_generation_runs
                SET next_attempt_at='2000-01-01T00:00:00.000Z'
                WHERE id=?
                """,
                (run["id"],),
            )
        second = process_class_commentary_student_generation_run(
            run["id"],
            memory_service=EmptyMemoryService(),
            generator=generator,
            charge_finalizer=flaky_charge,
            claim_owner="charge-retry",
        )
        self.assertEqual(second["status"], "succeeded")
        self.assertEqual(len(provider_calls), 1)
        self.assertEqual(self._usage_count(generation["id"]), 1)
        self.assertEqual(len({item[0] for item in charge_calls}), 1)
        self.assertEqual(len({item[1] for item in charge_calls}), 1)

    def test_manual_retry_of_charge_conflict_never_repeats_provider(self):
        generation = self._reserve("charge-conflict", students=[self.students[0]])
        run = lesson_manager.list_class_commentary_student_generation_runs(
            generation["id"]
        )[0]
        provider_calls = []

        def generator(**kwargs):
            provider_calls.append(kwargs["request_id"])
            return self._success_response(run["student_id"]), {
                "provider": "openai",
                "model": "deterministic-fake",
                "input_tokens": 60,
                "output_tokens": 30,
            }

        def conflict_charge(**kwargs):
            raise lesson_manager.AiUsageRequestConflict("payload conflict")

        first = process_class_commentary_student_generation_run(
            run["id"],
            memory_service=EmptyMemoryService(),
            generator=generator,
            charge_finalizer=conflict_charge,
            claim_owner="charge-conflict",
        )
        self.assertEqual(first["status"], "failed")
        self.assertEqual(len(provider_calls), 1)
        lesson_manager.retry_class_commentary_student_generation_runs(
            generation["id"],
            actor_user_id=self.teacher["id"],
            retry_request_id="charge-conflict-retry",
        )
        retried_run = lesson_manager.get_class_commentary_student_generation_run(
            run["id"]
        )
        self.assertEqual(retried_run["status"], "response_received")
        second = process_class_commentary_student_generation_run(
            run["id"],
            memory_service=EmptyMemoryService(),
            generator=generator,
            claim_owner="charge-conflict-retry",
        )
        self.assertEqual(second["status"], "succeeded")
        self.assertEqual(len(provider_calls), 1)
        self.assertEqual(self._usage_count(generation["id"]), 1)

    def test_rate_limit_retry_after_is_observable_and_reuses_request_identity(self):
        generation = self._reserve("rate-limit", students=[self.students[0]])
        run = lesson_manager.list_class_commentary_student_generation_runs(
            generation["id"]
        )[0]
        request_ids = []

        class RateLimitError(RuntimeError):
            def __init__(self):
                super().__init__("429 rate limit")
                self.headers = {"Retry-After": "90"}

        def limited(**kwargs):
            request_ids.append(kwargs["request_id"])
            raise RateLimitError()

        first = process_class_commentary_student_generation_run(
            run["id"],
            memory_service=EmptyMemoryService(),
            generator=limited,
            claim_owner="rate-limited",
        )
        self.assertEqual(first["status"], "retry_wait")
        waiting = lesson_manager.get_class_commentary_student_generation_run(run["id"])
        self.assertEqual(waiting["error_code"], "provider_rate_limited")
        self.assertTrue(waiting["next_attempt_at"])
        progress = lesson_manager.get_class_commentary_student_generation_progress(
            generation["id"]
        )
        self.assertEqual(progress["queued"], 1)
        self.assertEqual(progress["runs"][0]["error_code"], "provider_rate_limited")
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_student_generation_runs
                SET next_attempt_at='2000-01-01T00:00:00.000Z'
                WHERE id=?
                """,
                (run["id"],),
            )

        def recovered(**kwargs):
            request_ids.append(kwargs["request_id"])
            return self._success_response(run["student_id"]), {
                "provider": "openai",
                "model": "deterministic-fake",
                "input_tokens": 60,
                "output_tokens": 30,
            }

        second = process_class_commentary_student_generation_run(
            run["id"],
            memory_service=EmptyMemoryService(),
            generator=recovered,
            claim_owner="rate-limit-retry",
        )
        self.assertEqual(second["status"], "succeeded")
        self.assertEqual(len(set(request_ids)), 1)

    def test_generation_request_id_conflicts_on_any_frozen_payload_change(self):
        first = self._reserve("request-conflict")
        repeated = self._reserve("request-conflict")
        self.assertEqual(repeated["id"], first["id"])
        self.assertTrue(repeated["is_idempotent"])
        with self.assertRaises(lesson_manager.ClassCommentaryGenerationRequestConflict):
            self._reserve(
                "request-conflict",
                model_name="different-model",
            )

    def test_isolated_replay_uses_frozen_mode_after_kill_switch_change(self):
        first = self._reserve("isolated-replay-after-kill-switch")

        repeated = self._reserve(
            "isolated-replay-after-kill-switch",
            prompt_version="class-commentary-v1",
            structured_feedback_enabled=False,
            student_history_memory_mode="disabled_v1",
        )

        self.assertEqual(repeated["id"], first["id"])
        self.assertTrue(repeated["is_idempotent"])
        self.assertEqual(repeated["student_history_memory_mode"], "isolated_v2")
        self.assertEqual(
            repeated["prompt_version"],
            CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2,
        )

    def test_student_access_loss_fails_closed_before_memory_or_provider(self):
        generation = self._reserve("access-revoked", students=[self.students[0]])
        run = lesson_manager.list_class_commentary_student_generation_runs(
            generation["id"]
        )[0]
        lesson_manager.delete_or_archive_student_profile(
            self.students[0]["id"], self.teacher["organization_id"]
        )
        service = EmptyMemoryService()
        provider_calls = []
        result = process_class_commentary_student_generation_run(
            run["id"],
            memory_service=service,
            generator=lambda **kwargs: provider_calls.append(kwargs),
            claim_owner="access-revoked",
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(provider_calls, [])
        self.assertEqual(service.calls, [])
        self.assertEqual(
            lesson_manager.get_class_commentary_generation(generation["id"])["status"],
            "failed",
        )

    def test_student_run_history_forces_archive_instead_of_audit_orphaning(self):
        self._reserve("student-lifecycle", students=[self.students[0]])
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "DELETE FROM class_students WHERE student_id=?",
                (self.students[0]["id"],),
            )
            conn.execute(
                "DELETE FROM student_class_history WHERE student_id=?",
                (self.students[0]["id"],),
            )
        result = lesson_manager.delete_or_archive_student_profile(
            self.students[0]["id"], self.teacher["organization_id"]
        )
        self.assertEqual(result["action"], "archived")
        self.assertEqual(result["reference_count"], 1)

    def test_stale_worker_lease_exhaustion_fails_run_and_parent(self):
        generation = self._reserve("stale-lease", students=[self.students[0]])
        run = lesson_manager.list_class_commentary_student_generation_runs(
            generation["id"]
        )[0]
        claimed = lesson_manager.claim_class_commentary_student_generation_run(
            run["id"], claim_owner="lost-worker", lease_seconds=30
        )
        self.assertEqual(claimed["attempt_count"], 1)
        with lesson_manager.get_conn() as conn:
            conn.execute(
                """
                UPDATE class_commentary_student_generation_runs
                SET next_attempt_at='2000-01-01T00:00:00.000Z'
                WHERE id=?
                """,
                (run["id"],),
            )
        recovered = lesson_manager.recover_stale_class_commentary_student_generation_runs(
            now="2000-01-02T00:00:00.000Z", max_attempts=1
        )
        self.assertEqual(recovered, [run["id"]])
        saved_run = lesson_manager.get_class_commentary_student_generation_run(run["id"])
        self.assertEqual(saved_run["status"], "failed")
        self.assertEqual(saved_run["error_code"], "worker_lease_attempts_exhausted")
        self.assertEqual(
            lesson_manager.get_class_commentary_generation(generation["id"])["status"],
            "failed",
        )

    def test_current_evidence_is_exact_provenance_and_never_uses_ambiguous_segments(self):
        roster = [
            {"student_id": item["id"], "student_name": item["name"]}
            for item in self.students
        ]
        snapshot = build_student_current_evidence(
            transcript=self.transcript,
            transcript_hash=content_hash(self.transcript),
            roster=roster,
            target_student_id=self.students[0]["id"],
            matcher_version=CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V1,
        )
        texts = [item["text"] for item in snapshot["fragments"]]
        self.assertEqual(texts, ["甲同学移项步骤清楚。"])
        self.assertNotIn("一起讨论", "".join(texts))
        self.assertNotIn("近音", "".join(texts))
        for fragment in snapshot["fragments"]:
            self.assertEqual(
                self.transcript[fragment["start"] : fragment["end"]],
                fragment["text"],
            )
            self.assertEqual(content_hash(fragment["text"]), fragment["text_hash"])


class FakeScopedMemoryService:
    enabled = True

    def __init__(self, *, style=None, students=None):
        self.settings = SimpleNamespace(
            context_char_limit=3000, style_limit=5, student_limit=5
        )
        self.style = style or []
        self.students = students or {}
        self.calls = []

    def search_style(self, query, **scope):
        self.calls.append(("style", query, scope))
        return list(self.style)

    def search_student(self, query, **scope):
        self.calls.append(("student", query, scope))
        return list(self.students.get(scope["student_id"], []))


def memory_candidate(record_id, record_version, memory_type, **scope):
    return {
        "id": f"mem0-{record_id}",
        "memory": "untrusted projection text",
        "metadata": {
            "organization_id": 4,
            "memory_record_id": record_id,
            "record_version": record_version,
            "evidence_count": 1,
            "memory_type": memory_type,
            "status": "active",
            "scope_skill_registry_id": None,
            "student_id": None,
            "subject_key": None,
            **scope,
        },
    }


def memory_record(record_id, memory_type, text, **scope):
    return {
        "id": record_id,
        "organization_id": 4,
        "memory_type": memory_type,
        "scope_skill_registry_id": None,
        "student_id": None,
        "subject_key": None,
        "desired_status": "active",
        "applied_status": "active",
        "mem0_memory_id": f"mem0-{record_id}",
        "record_version": 1,
        "active_evidence_count": 1,
        "active_evidence": [
            {
                "evidence_id": record_id + 100,
                "revision_id": record_id + 200,
                "evidence_hash": f"evidence-{record_id}",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
        "confidence": 0.9,
        "memory_text": text,
        "created_from_revision_id": record_id + 200,
        "created_at": f"2026-01-{record_id:02d}T00:00:00Z",
        **scope,
    }


class ClassCommentaryIsolatedMemoryRetrievalV2Test(unittest.TestCase):
    def setUp(self):
        self.generation = {
            "organization_id": 4,
            "skill_registry_id": 8,
            "subject_key": "math",
        }
        self.evidence = {
            "schema_version": "class_commentary.student_current_evidence.v1",
            "matcher_version": CLASS_COMMENTARY_STUDENT_EVIDENCE_MATCHER_V1,
            "transcript_hash": "transcript-hash",
            "attribution": "exact_frozen_roster_name",
            "fragments": [
                {"start": 0, "end": 4, "text": "当前证据", "text_hash": "hash"}
            ],
        }
        self.class_context = {"subject_key": "math"}

    def test_scope_recheck_keeps_only_target_and_reconciles_stale_projection(self):
        style = memory_candidate(
            10, 1, "teacher_style", scope_skill_registry_id=8
        )
        target = memory_candidate(
            11, 1, "student_fact", student_id=21, subject_key="math"
        )
        foreign = memory_candidate(
            12, 1, "student_fact", student_id=22, subject_key="math"
        )
        service = FakeScopedMemoryService(
            style=[style], students={21: [target, foreign]}
        )
        records = {
            10: memory_record(
                10,
                "teacher_style",
                "每条建议使用一个短句.",
                scope_skill_registry_id=8,
            ),
            11: memory_record(
                11,
                "student_fact",
                "过去常在移项时漏写负号.",
                student_id=21,
                subject_key="math",
            ),
            12: memory_record(
                12,
                "student_fact",
                "另一个学生的私有事实.",
                student_id=22,
                subject_key="math",
            ),
        }
        marked = []
        context = retrieve_isolated_student_memory_context(
            generation=self.generation,
            student_id=21,
            evidence_snapshot=self.evidence,
            class_context=self.class_context,
            memory_service=service,
            record_loader=lambda ids: [records[item] for item in ids],
            reconciliation_marker=lambda org, ids, reason: marked.append(
                (org, ids, reason)
            ),
        )
        self.assertEqual(
            [item["memory_record_id"] for item in context["records"]], [10, 11]
        )
        self.assertNotIn("untrusted projection text", canonical_json(context))
        self.assertNotIn("另一个学生的私有事实", canonical_json(context))
        self.assertEqual(marked, [(4, [12], "retrieval_projection_mismatch")])
        self.assertEqual(service.calls[1][2], {
            "organization_id": 4,
            "student_id": 21,
            "subject_key": "math",
        })

    def test_revoked_superseded_wrong_org_subject_and_version_are_all_discarded(self):
        candidates = [
            memory_candidate(
                record_id, 1, "student_fact", student_id=21, subject_key="math"
            )
            for record_id in range(21, 26)
        ]
        candidates[2]["metadata"]["organization_id"] = 5
        candidates[3]["metadata"]["subject_key"] = "science"
        candidates[4]["metadata"]["record_version"] = 9
        records = {
            record_id: memory_record(
                record_id,
                "student_fact",
                f"stale-{record_id}",
                student_id=21,
                subject_key="math",
            )
            for record_id in range(21, 26)
        }
        records[21]["desired_status"] = "revoked"
        records[22]["desired_status"] = "superseded"
        marked = []
        context = retrieve_isolated_student_memory_context(
            generation=self.generation,
            student_id=21,
            evidence_snapshot=self.evidence,
            class_context=self.class_context,
            memory_service=FakeScopedMemoryService(students={21: candidates}),
            record_loader=lambda ids: [records[item] for item in ids],
            reconciliation_marker=lambda org, ids, reason: marked.append(
                (org, ids, reason)
            ),
        )
        self.assertEqual(context["student_history_memories"], [])
        self.assertEqual(
            marked,
            [(4, [21, 22, 23, 24, 25], "retrieval_projection_mismatch")],
        )

    def test_configured_student_memory_limit_is_enforced_after_mem0(self):
        candidates = [
            memory_candidate(
                record_id, 1, "student_fact", student_id=21, subject_key="math"
            )
            for record_id in range(31, 39)
        ]
        records = {
            record_id: memory_record(
                record_id,
                "student_fact",
                f"history-{record_id}",
                student_id=21,
                subject_key="math",
            )
            for record_id in range(31, 39)
        }
        service = FakeScopedMemoryService(students={21: candidates})
        service.settings.student_limit = 3
        context = retrieve_isolated_student_memory_context(
            generation=self.generation,
            student_id=21,
            evidence_snapshot=self.evidence,
            class_context=self.class_context,
            memory_service=service,
            record_loader=lambda ids: [records[item] for item in ids],
        )
        self.assertEqual(
            [item["memory_record_id"] for item in context["student_history_memories"]],
            [31, 32, 33],
        )

    def test_conflicting_history_stays_separate_with_source_and_time(self):
        first = memory_candidate(
            11, 1, "student_fact", student_id=21, subject_key="math"
        )
        second = memory_candidate(
            13, 1, "student_fact", student_id=21, subject_key="math"
        )
        records = {
            11: memory_record(
                11,
                "student_fact",
                "过去需要提醒验算.",
                student_id=21,
                subject_key="math",
            ),
            13: memory_record(
                13,
                "student_fact",
                "最近一次记录显示能主动验算.",
                student_id=21,
                subject_key="math",
            ),
        }
        context = retrieve_isolated_student_memory_context(
            generation=self.generation,
            student_id=21,
            evidence_snapshot=self.evidence,
            class_context=self.class_context,
            memory_service=FakeScopedMemoryService(students={21: [first, second]}),
            record_loader=lambda ids: [records[item] for item in ids],
        )
        history = context["student_history_memories"]
        self.assertEqual(len(history), 2)
        self.assertEqual(
            [item["created_from_revision_id"] for item in history], [211, 213]
        )
        self.assertTrue(all(item["created_at"] for item in history))
        prompt = build_isolated_student_chat_request(
            student_id=21,
            student_name="甲同学",
            class_context=self.class_context,
            evidence_snapshot=self.evidence,
            student_history_memories=history,
            teacher_style_memories=[],
            skill_content="",
            model_parameters={"temperature": 0.55},
        )
        prompt_text = prompt["messages"][1]["content"]
        self.assertIn("过去需要提醒验算", prompt_text)
        self.assertIn("最近一次记录显示能主动验算", prompt_text)
        self.assertIn("source_time", prompt_text)
        self.assertNotIn("memory_record_id", prompt_text)
        self.assertNotIn("mem0_memory_id", prompt_text)
        self.assertNotIn("source_revision_id", prompt_text)

    def test_teacher_style_can_be_reused_but_student_history_cannot_cross_scope(self):
        style = memory_candidate(
            10, 1, "teacher_style", scope_skill_registry_id=8
        )
        student_a = memory_candidate(
            11, 1, "student_fact", student_id=21, subject_key="math"
        )
        student_b = memory_candidate(
            12, 1, "student_fact", student_id=22, subject_key="math"
        )
        records = {
            10: memory_record(
                10,
                "teacher_style",
                "建议以动词开头.",
                scope_skill_registry_id=8,
            ),
            11: memory_record(
                11,
                "student_fact",
                "甲的历史事实.",
                student_id=21,
                subject_key="math",
            ),
            12: memory_record(
                12,
                "student_fact",
                "乙的历史事实.",
                student_id=22,
                subject_key="math",
            ),
        }
        service = FakeScopedMemoryService(
            style=[style], students={21: [student_a], 22: [student_b]}
        )
        contexts = {}
        for student_id in (21, 22):
            contexts[student_id] = retrieve_isolated_student_memory_context(
                generation=self.generation,
                student_id=student_id,
                evidence_snapshot=self.evidence,
                class_context=self.class_context,
                memory_service=service,
                record_loader=lambda ids: [records[item] for item in ids],
            )
        self.assertEqual(
            contexts[21]["teacher_style_memories"][0]["memory_text"],
            contexts[22]["teacher_style_memories"][0]["memory_text"],
        )
        self.assertEqual(
            [item["memory_text"] for item in contexts[21]["student_history_memories"]],
            ["甲的历史事实."],
        )
        self.assertEqual(
            [item["memory_text"] for item in contexts[22]["student_history_memories"]],
            ["乙的历史事实."],
        )

    def test_subject_missing_degrades_without_guessing_or_searching(self):
        service = FakeScopedMemoryService()
        context = retrieve_isolated_student_memory_context(
            generation={**self.generation, "subject_key": ""},
            student_id=21,
            evidence_snapshot=self.evidence,
            class_context={"subject_key": ""},
            memory_service=service,
            record_loader=lambda ids: [],
        )
        self.assertEqual(context["retrieval_status"], "degraded")
        self.assertEqual(context["degraded_reason"], "subject_unavailable")
        self.assertEqual(context["student_history_memories"], [])
        self.assertEqual(service.calls, [])

    def test_snapshot_revalidation_rejects_revoked_or_changed_evidence(self):
        candidate = memory_candidate(
            11, 1, "student_fact", student_id=21, subject_key="math"
        )
        record = memory_record(
            11,
            "student_fact",
            "过去常在移项时漏写负号.",
            student_id=21,
            subject_key="math",
        )
        context = retrieve_isolated_student_memory_context(
            generation=self.generation,
            student_id=21,
            evidence_snapshot=self.evidence,
            class_context=self.class_context,
            memory_service=FakeScopedMemoryService(students={21: [candidate]}),
            record_loader=lambda ids: [dict(record)],
        )
        validate_isolated_student_memory_context_snapshot(
            generation=self.generation,
            student_id=21,
            memory_context=context,
            record_loader=lambda ids: [dict(record)],
        )
        revoked = {**record, "desired_status": "revoked", "active_evidence": []}
        with self.assertRaises(ClassCommentaryStudentMemoryRetrievalError):
            validate_isolated_student_memory_context_snapshot(
                generation=self.generation,
                student_id=21,
                memory_context=context,
                record_loader=lambda ids: [revoked],
            )

    def test_prompt_privacy_rejects_other_identity_and_private_values(self):
        prompt = build_isolated_student_chat_request(
            student_id=21,
            student_name="甲同学",
            class_context=build_safe_class_context(
                class_record={"id": 99}, subject_key="math"
            ),
            evidence_snapshot=self.evidence,
            student_history_memories=[],
            teacher_style_memories=[],
            skill_content="",
            model_parameters={"temperature": 0.55},
        )
        validate_isolated_prompt_privacy(
            chat_request=prompt,
            target_student_id=21,
            target_student_name="甲同学",
            other_students=[{"student_id": 22, "student_name": "乙同学"}],
            forbidden_private_values=["乙的私有证据"],
        )
        contaminated = json.loads(json.dumps(prompt, ensure_ascii=False))
        contaminated["messages"][1]["content"] += "\n乙的私有证据"
        with self.assertRaises(ValueError):
            validate_isolated_prompt_privacy(
                chat_request=contaminated,
                target_student_id=21,
                target_student_name="甲同学",
                other_students=[{"student_id": 22, "student_name": "乙同学"}],
                forbidden_private_values=["乙的私有证据"],
            )


if __name__ == "__main__":
    unittest.main()
