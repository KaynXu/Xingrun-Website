from __future__ import annotations

import copy
import hashlib
import json
import threading
import unittest
from unittest.mock import patch

from class_commentary_batch_generation_jobs import (
    _default_generator,
    _fallback_generation_request,
    _merge_feedback_responses,
    process_class_commentary_batch_generation,
)
from class_commentary_feedback_schema import (
    ClassCommentaryStructuredFeedbackValidationError,
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class FakeBatchGenerationStore:
    def __init__(
        self,
        *,
        generation_id: int = 41,
        attempt_count: int = 0,
        response: dict | None = None,
        hold_status: str = "active",
        usage_id: int | None = None,
        dispatch_status: str | None = None,
    ):
        self._lock = threading.Lock()
        self.prompt = {
            "messages": [
                {"role": "system", "content": "Return the frozen class JSON."},
                {"role": "user", "content": "[STUDENT_CONTEXTS_BY_ID]\n[]"},
            ],
            "temperature": 0.2,
        }
        prompt_json = _canonical_json(self.prompt)
        self.generation = {
            "id": generation_id,
            "organization_id": 7,
            "teacher_user_id": 11,
            "status": "generating",
            "execution_snapshot_status": "ready",
            "prompt_payload_snapshot_json": prompt_json,
            "prompt_payload_hash": hashlib.sha256(
                prompt_json.encode("utf-8")
            ).hexdigest(),
            "model_provider": "openai",
            "model_name": "frozen-model",
            "batch_attempt_count": attempt_count,
            "batch_provider_dispatch_status": (
                dispatch_status
                if dispatch_status is not None
                else "started"
                if response is not None
                else "pending"
            ),
            "batch_claim_token": None,
            "batch_claim_owner": None,
        }
        self.response = copy.deepcopy(response)
        self.hold = {
            "status": hold_status,
            "request_id": "credit-hold-request",
            "request_payload_hash": "credit-hold-payload-hash",
            "usage_id": usage_id,
        }
        self.validated = False
        self.claim_calls: list[dict] = []
        self.persist_calls: list[dict] = []
        self.dispatch_start_calls: list[str] = []
        self.validation_calls: list[str] = []
        self.charge_calls: list[dict] = []
        self.complete_calls: list[dict] = []
        self.release_calls: list[str] = []
        self.terminal_failure_calls: list[str] = []
        self.terminal_failure_snapshots: list[dict | None] = []
        self.validation_failure_calls: list[str] = []
        self.validation_failure_snapshots: list[dict | None] = []
        self.persist_raises_after_write = False
        self.charge_raises_after_settlement = False
        self.complete_failures = 0

    def _generation_copy(self) -> dict:
        return copy.deepcopy(self.generation)

    def claim_class_commentary_batch_generation(
        self,
        generation_id: int,
        *,
        claim_owner: str,
        lease_seconds: int,
    ) -> dict | None:
        with self._lock:
            self.claim_calls.append(
                {
                    "generation_id": generation_id,
                    "claim_owner": claim_owner,
                    "lease_seconds": lease_seconds,
                }
            )
            if (
                generation_id != self.generation["id"]
                or self.generation["status"] != "generating"
                or self.generation["batch_claim_token"] is not None
                or self.hold["status"] not in {"active", "settled"}
            ):
                return None
            self.generation["batch_attempt_count"] += 1
            claim_token = (
                f"batch-claim-{self.generation['batch_attempt_count']}"
            )
            self.generation["batch_claim_token"] = claim_token
            self.generation["batch_claim_owner"] = claim_owner
            return self._generation_copy()

    def get_class_commentary_generation(self, generation_id: int) -> dict | None:
        with self._lock:
            if generation_id != self.generation["id"]:
                return None
            return self._generation_copy()

    def get_class_commentary_generation_credit_hold(
        self, generation_id: int
    ) -> dict | None:
        if generation_id != self.generation["id"]:
            return None
        return copy.deepcopy(self.hold)

    def get_class_commentary_batch_generation_response(
        self, generation_id: int
    ) -> dict | None:
        if generation_id != self.generation["id"]:
            return None
        return copy.deepcopy(self.response)

    def mark_class_commentary_batch_provider_dispatch_started(
        self,
        generation_id: int,
        *,
        claim_token: str,
    ) -> dict:
        self._assert_current_claim(generation_id, claim_token)
        if self.generation["batch_provider_dispatch_status"] != "pending":
            raise AssertionError("provider dispatch was started more than once")
        self.dispatch_start_calls.append(claim_token)
        self.generation["batch_provider_dispatch_status"] = "started"
        return self._generation_copy()

    def persist_class_commentary_batch_generation_response(
        self,
        generation_id: int,
        *,
        response_text: str,
        usage: dict,
        claim_token: str,
    ) -> dict:
        self._assert_current_claim(generation_id, claim_token)
        payload = {
            "response_text": response_text,
            "usage": copy.deepcopy(usage),
        }
        self.persist_calls.append(copy.deepcopy(payload))
        self.response = payload
        if self.persist_raises_after_write:
            self.persist_raises_after_write = False
            raise RuntimeError("crash after durable response persistence")
        return self._generation_copy()

    def validate_class_commentary_batch_generation_response(
        self,
        generation_id: int,
        *,
        claim_token: str,
    ) -> dict:
        self._assert_current_claim(generation_id, claim_token)
        if self.response is None:
            raise AssertionError("validation ran without a persisted response")
        self.validation_calls.append(claim_token)
        self.validated = True
        return self._generation_copy()

    def finalize_charge(self, **kwargs) -> dict:
        if self.hold["status"] != "active":
            raise AssertionError("charge was repeated after settlement")
        self.charge_calls.append(copy.deepcopy(kwargs))
        self.hold["status"] = "settled"
        self.hold["usage_id"] = 701
        if self.charge_raises_after_settlement:
            self.charge_raises_after_settlement = False
            raise RuntimeError("crash after durable charge settlement")
        return {"id": 701}

    def complete_class_commentary_batch_generation(
        self,
        generation_id: int,
        *,
        charge_usage_id: int,
        claim_token: str,
    ) -> dict:
        self._assert_current_claim(generation_id, claim_token)
        self.complete_calls.append(
            {
                "charge_usage_id": charge_usage_id,
                "claim_token": claim_token,
            }
        )
        if self.complete_failures:
            self.complete_failures -= 1
            raise RuntimeError("crash before durable publish")
        if not self.validated:
            raise AssertionError("generation was published before validation")
        if (
            self.hold["status"] != "settled"
            or int(self.hold["usage_id"] or 0) != charge_usage_id
        ):
            raise AssertionError("generation was published before charge settlement")
        self.generation["status"] = "succeeded"
        self.generation["batch_claim_token"] = None
        self.generation["batch_claim_owner"] = None
        return self._generation_copy()

    def release_class_commentary_batch_generation_claim(
        self,
        generation_id: int,
        *,
        claim_token: str,
    ) -> dict:
        if generation_id != self.generation["id"]:
            raise AssertionError("wrong generation released")
        self.release_calls.append(claim_token)
        if self.generation["batch_claim_token"] == claim_token:
            self.generation["batch_claim_token"] = None
            self.generation["batch_claim_owner"] = None
        return self._generation_copy()

    def fail_class_commentary_batch_generation_terminal(
        self,
        generation_id: int,
        *,
        claim_token: str,
        error_code: str,
        provider_failure: object = None,
    ) -> dict:
        self._assert_current_claim(generation_id, claim_token)
        if self.hold["status"] == "settled":
            raise AssertionError("settled hold must be published")
        self.terminal_failure_calls.append(error_code)
        self.terminal_failure_snapshots.append(copy.deepcopy(provider_failure))
        self.hold["status"] = "released"
        self.generation["status"] = "failed"
        self.generation["error_code"] = error_code
        self.generation["batch_claim_token"] = None
        self.generation["batch_claim_owner"] = None
        return self._generation_copy()

    def fail_class_commentary_batch_generation_validation(
        self,
        generation_id: int,
        *,
        claim_token: str,
        error_code: str,
        validation_failure: object = None,
    ) -> dict:
        self._assert_current_claim(generation_id, claim_token)
        self.validation_failure_calls.append(error_code)
        self.validation_failure_snapshots.append(copy.deepcopy(validation_failure))
        self.hold["status"] = "released"
        self.generation["status"] = "failed"
        self.generation["error_code"] = error_code
        self.generation["batch_claim_token"] = None
        self.generation["batch_claim_owner"] = None
        return self._generation_copy()

    def _assert_current_claim(
        self, generation_id: int, claim_token: str
    ) -> None:
        if generation_id != self.generation["id"]:
            raise AssertionError("wrong generation")
        if claim_token != self.generation["batch_claim_token"]:
            raise AssertionError("claim token was not forwarded")


class ClassCommentaryBatchGenerationJobsTest(unittest.TestCase):
    usage = {
        "provider": "openai",
        "model": "frozen-model",
        "input_tokens": 80,
        "output_tokens": 40,
    }

    @staticmethod
    def _provider_response() -> tuple[str, dict]:
        return '{"schema_version":"class_commentary.student_feedback.v1"}', copy.deepcopy(
            ClassCommentaryBatchGenerationJobsTest.usage
        )

    @staticmethod
    def _run(store: FakeBatchGenerationStore, **kwargs) -> dict:
        return process_class_commentary_batch_generation(
            store.generation["id"],
            store=store,
            runtime_config={
                "class_commentary_batch_generation_timeout": 120,
            },
            claim_owner="worker-a",
            **kwargs,
        )

    def test_default_provider_dispatch_disables_sdk_retries(self):
        generation = {
            "id": 41,
            "model_provider": "openai",
            "model_name": "frozen-model",
        }
        chat_request = {
            "messages": [{"role": "user", "content": "frozen"}],
            "temperature": 0.2,
        }
        config = {
            "class_commentary_openai_api_key": "test-key",
            "class_commentary_openai_base_url": "https://example.invalid",
            "class_commentary_openai_headers": "",
            "class_commentary_batch_generation_timeout": 120,
        }

        with patch(
            "class_commentary_batch_generation_jobs.ai_processor.generate_class_commentary_feedback",
            return_value=self._provider_response(),
        ) as generate:
            _default_generator(generation, chat_request, config)

        self.assertEqual(generate.call_count, 1)
        self.assertEqual(generate.call_args.kwargs["max_retries"], 0)
        self.assertEqual(generate.call_args.kwargs["request_timeout"], 120.0)

    def test_ready_frozen_prompt_calls_provider_once_with_stable_request_id(self):
        store = FakeBatchGenerationStore()
        provider_calls = []

        def generator(**kwargs):
            provider_calls.append(copy.deepcopy(kwargs))
            return self._provider_response()

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(provider_calls), 1)
        self.assertEqual(provider_calls[0]["chat_request"], store.prompt)
        self.assertEqual(
            provider_calls[0]["request_id"],
            f"class-commentary-generation-{store.generation['id']}",
        )
        self.assertEqual(provider_calls[0]["provider"], "openai")
        self.assertEqual(provider_calls[0]["model"], "frozen-model")
        self.assertEqual(store.dispatch_start_calls, ["batch-claim-1"])
        self.assertEqual(len(store.persist_calls), 1)
        self.assertEqual(len(store.charge_calls), 1)
        self.assertEqual(len(store.complete_calls), 1)

    def test_pending_snapshot_is_prepared_under_claim_before_provider(self):
        store = FakeBatchGenerationStore()
        store.generation["execution_snapshot_status"] = "pending"
        store.generation["prompt_payload_snapshot_json"] = "{}"
        store.generation["prompt_payload_hash"] = hashlib.sha256(
            b"{}"
        ).hexdigest()
        prepared_calls = []

        def prepare(**kwargs):
            prepared_calls.append(copy.deepcopy(kwargs["generation"]))
            self.assertTrue(kwargs["generation"]["batch_claim_token"])
            store.generation["execution_snapshot_status"] = "ready"
            store.generation["prompt_payload_snapshot_json"] = _canonical_json(
                store.prompt
            )
            store.generation["prompt_payload_hash"] = hashlib.sha256(
                store.generation["prompt_payload_snapshot_json"].encode("utf-8")
            ).hexdigest()
            return store._generation_copy()

        with patch(
            "class_commentary_batch_generation_jobs._prepare_execution_snapshot",
            side_effect=prepare,
        ):
            result = self._run(
                store,
                generator=lambda **_kwargs: self._provider_response(),
                charge_finalizer=store.finalize_charge,
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(prepared_calls), 1)
        self.assertEqual(store.generation["execution_snapshot_status"], "ready")
        self.assertEqual(store.dispatch_start_calls, ["batch-claim-1"])

    def test_ready_snapshot_never_rebuilds_memory_or_graph_context(self):
        store = FakeBatchGenerationStore()
        with patch(
            "class_commentary_batch_generation_jobs._prepare_execution_snapshot",
            side_effect=AssertionError("ready snapshot was rebuilt"),
        ) as prepare:
            result = self._run(
                store,
                generator=lambda **_kwargs: self._provider_response(),
                charge_finalizer=store.finalize_charge,
            )

        self.assertEqual(result["status"], "succeeded")
        prepare.assert_not_called()

    def test_persisted_response_skips_provider_and_validation_gets_claim_token(self):
        store = FakeBatchGenerationStore(
            response={"response_text": "already durable", "usage": self.usage}
        )

        result = self._run(
            store,
            generator=lambda **_kwargs: self.fail("provider was called again"),
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(store.dispatch_start_calls, [])
        self.assertEqual(store.persist_calls, [])
        self.assertEqual(store.validation_calls, ["batch-claim-1"])
        self.assertEqual(store.complete_calls[0]["claim_token"], "batch-claim-1")

    def test_settled_hold_only_publishes_and_never_charges_again(self):
        store = FakeBatchGenerationStore(
            response={"response_text": "already durable", "usage": self.usage},
            hold_status="settled",
            usage_id=909,
        )
        store.validated = True

        result = self._run(
            store,
            generator=lambda **_kwargs: self.fail("provider was called again"),
            charge_finalizer=lambda **_kwargs: self.fail("charge was repeated"),
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(store.charge_calls, [])
        self.assertEqual(store.complete_calls[0]["charge_usage_id"], 909)

    def test_provider_exception_fails_closed_without_retrying(self):
        store = FakeBatchGenerationStore()
        provider_calls = 0

        def generator(**_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            raise TimeoutError("provider timed out")

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "provider_timeout")
        self.assertEqual(provider_calls, 1)
        self.assertEqual(store.generation["status"], "failed")
        self.assertIsNone(store.generation["batch_claim_token"])
        self.assertEqual(store.hold["status"], "released")
        self.assertEqual(
            store.terminal_failure_calls,
            ["provider_timeout"],
        )
        self.assertEqual(
            store.terminal_failure_snapshots[0]["result_state"],
            "unknown",
        )
        self.assertEqual(
            store.terminal_failure_snapshots[0]["exception_type"],
            "builtins.TimeoutError",
        )
        self.assertEqual(store.release_calls, [])

    def test_validation_failure_preserves_specific_safe_diagnostics(self):
        store = FakeBatchGenerationStore()

        def reject_response(_generation_id: int, *, claim_token: str) -> dict:
            store._assert_current_claim(store.generation["id"], claim_token)
            raise ClassCommentaryStructuredFeedbackValidationError(
                "student_feedback_missing_skill_emoji",
                student_id=23,
                field="feedback_text",
                limit=1,
            )

        store.validate_class_commentary_batch_generation_response = reject_response
        result = self._run(
            store,
            generator=lambda **_kwargs: self._provider_response(),
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            result["error_code"], "student_feedback_missing_skill_emoji"
        )
        self.assertEqual(store.hold["status"], "released")
        self.assertEqual(store.charge_calls, [])
        self.assertEqual(
            store.validation_failure_snapshots,
            [
                {
                    "error_code": "student_feedback_missing_skill_emoji",
                    "student_id": 23,
                    "field": "feedback_text",
                    "limit": 1,
                }
            ],
        )

    def test_started_dispatch_without_response_never_calls_provider_again(self):
        store = FakeBatchGenerationStore(dispatch_status="started")
        provider_calls = 0

        def generator(**_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return self._provider_response()

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "provider_dispatch_interrupted")
        self.assertEqual(provider_calls, 0)
        self.assertEqual(store.generation["status"], "failed")
        self.assertEqual(
            store.generation["error_code"],
            "provider_dispatch_interrupted",
        )
        self.assertIsNone(store.generation["batch_claim_token"])
        self.assertEqual(store.hold["status"], "released")
        self.assertEqual(
            store.terminal_failure_calls,
            ["provider_dispatch_interrupted"],
        )
        self.assertEqual(
            store.terminal_failure_snapshots[0]["result_state"],
            "unknown",
        )
        self.assertEqual(store.release_calls, [])

    def test_legacy_unknown_dispatch_without_response_never_calls_provider(self):
        store = FakeBatchGenerationStore(dispatch_status="legacy_unknown")
        provider_calls = 0

        def generator(**_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return self._provider_response()

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            result["error_code"],
            "provider_dispatch_legacy_unknown",
        )
        self.assertEqual(provider_calls, 0)
        self.assertEqual(store.hold["status"], "released")

    def test_second_worker_cannot_execute_while_first_claim_is_live(self):
        store = FakeBatchGenerationStore()
        nested_results = []
        provider_calls = 0

        def generator(**_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            nested_results.append(
                self._run(
                    store,
                    generator=lambda **_inner: self.fail(
                        "second provider call was allowed"
                    ),
                    charge_finalizer=store.finalize_charge,
                )
            )
            return self._provider_response()

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(provider_calls, 1)
        self.assertEqual(nested_results[0]["status"], "not_claimed")
        self.assertEqual(len(store.persist_calls), 1)
        self.assertEqual(len(store.charge_calls), 1)

    def test_crash_after_response_persistence_resumes_without_provider_replay(self):
        store = FakeBatchGenerationStore()
        store.persist_raises_after_write = True
        provider_calls = 0

        def generator(**_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return self._provider_response()

        with self.assertRaisesRegex(RuntimeError, "durable response persistence"):
            self._run(
                store,
                generator=generator,
                charge_finalizer=store.finalize_charge,
            )

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(provider_calls, 1)
        self.assertEqual(len(store.persist_calls), 1)
        self.assertEqual(len(store.charge_calls), 1)

    def test_crash_after_charge_settlement_resumes_without_provider_or_charge_replay(self):
        store = FakeBatchGenerationStore()
        store.charge_raises_after_settlement = True
        provider_calls = 0

        def generator(**_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return self._provider_response()

        with self.assertRaisesRegex(RuntimeError, "durable charge settlement"):
            self._run(
                store,
                generator=generator,
                charge_finalizer=store.finalize_charge,
            )

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(provider_calls, 1)
        self.assertEqual(len(store.charge_calls), 1)
        self.assertEqual(store.complete_calls[-1]["charge_usage_id"], 701)

    def test_publish_crash_resumes_from_settled_usage_without_replaying_side_effects(self):
        store = FakeBatchGenerationStore()
        store.complete_failures = 1
        provider_calls = 0

        def generator(**_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return self._provider_response()

        with self.assertRaisesRegex(RuntimeError, "durable publish"):
            self._run(
                store,
                generator=generator,
                charge_finalizer=store.finalize_charge,
            )

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(provider_calls, 1)
        self.assertEqual(len(store.charge_calls), 1)
        self.assertEqual(len(store.complete_calls), 2)

    def test_coverage_gap_triggers_one_correction_regeneration(self):
        store = FakeBatchGenerationStore()
        store.generation["attending_roster_snapshot_json"] = json.dumps(
            [
                {"student_id": 1, "student_name": "甲"},
                {"student_id": 2, "student_name": "乙"},
            ]
        )
        calls = []

        def generator(**kwargs):
            calls.append(copy.deepcopy(kwargs))
            if len(calls) == 1:
                return (
                    '{"schema_version":"class_commentary.student_feedback.v1",'
                    '"items":[{"student_id":1,"feedback_text":"甲不错"}]}',
                    copy.deepcopy(self.usage),
                )
            return (
                '{"schema_version":"class_commentary.student_feedback.v1",'
                '"items":[{"student_id":1,"feedback_text":"甲不错"},'
                '{"student_id":2,"feedback_text":"乙加油"}]}',
                copy.deepcopy(self.usage),
            )

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(calls), 2)
        second_messages = str(
            calls[1].get("chat_request", {}).get("messages") or ""
        )
        self.assertIn("遗漏", second_messages)
        self.assertIn("2", second_messages)
        self.assertEqual(len(store.persist_calls), 1)
        self.assertIn("乙加油", str(store.persist_calls[0].get("response_text") or ""))

    def test_coverage_gap_without_roster_snapshot_keeps_single_call(self):
        store = FakeBatchGenerationStore()
        provider_calls = 0

        def generator(**_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return self._provider_response()

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(provider_calls, 1)

    def test_merge_feedback_responses_fills_gaps_from_first_version(self):
        first = (
            '{"schema_version":"class_commentary.student_feedback.v1",'
            '"items":[{"student_id":1,"feedback_text":"甲"}]}'
        )
        second = (
            '{"schema_version":"class_commentary.student_feedback.v1",'
            '"items":[{"student_id":2,"feedback_text":"乙"}]}'
        )
        merged = _merge_feedback_responses(
            first_text=first,
            second_text=second,
            fallback_text=second,
        )
        parsed = json.loads(merged)
        self.assertEqual(
            {int(item["student_id"]) for item in parsed["items"]},
            {1, 2},
        )
        self.assertEqual(
            {int(item["student_id"]): item["feedback_text"] for item in parsed["items"]},
            {1: "甲", 2: "乙"},
        )

    def test_coverage_gap_merges_both_versions_to_cover_roster(self):
        store = FakeBatchGenerationStore()
        store.generation["attending_roster_snapshot_json"] = json.dumps(
            [
                {"student_id": 1, "student_name": "甲"},
                {"student_id": 2, "student_name": "乙"},
            ]
        )
        calls = []

        def generator(**kwargs):
            calls.append(copy.deepcopy(kwargs))
            if len(calls) == 1:
                return (
                    '{"schema_version":"class_commentary.student_feedback.v1",'
                    '"items":[{"student_id":1,"feedback_text":"甲不错"}]}',
                    copy.deepcopy(self.usage),
                )
            return (
                '{"schema_version":"class_commentary.student_feedback.v1",'
                '"items":[{"student_id":2,"feedback_text":"乙加油"}]}',
                copy.deepcopy(self.usage),
            )

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(store.persist_calls), 1)
        persisted = json.loads(store.persist_calls[0]["response_text"])
        self.assertEqual(
            {int(item["student_id"]) for item in persisted["items"]},
            {1, 2},
        )

    def test_targeted_completion_recovers_students_missed_by_both_full_versions(self):
        store = FakeBatchGenerationStore()
        store.generation["attending_roster_snapshot_json"] = json.dumps(
            [
                {"student_id": 1, "student_name": "甲"},
                {"student_id": 2, "student_name": "乙"},
            ]
        )
        calls = []

        def generator(**kwargs):
            calls.append(copy.deepcopy(kwargs))
            index = len(calls)
            if index == 1:
                return (
                    '{"schema_version":"class_commentary.student_feedback.v1",'
                    '"items":[{"student_id":1,"feedback_text":"甲不错"}]}',
                    copy.deepcopy(self.usage),
                )
            if index == 2:
                return (
                    '{"schema_version":"class_commentary.student_feedback.v1",'
                    '"items":[{"student_id":1,"feedback_text":"甲不错"}]}',
                    copy.deepcopy(self.usage),
                )
            return (
                '{"schema_version":"class_commentary.student_feedback.v1",'
                '"items":[{"student_id":2,"feedback_text":"乙加油"}]}',
                copy.deepcopy(self.usage),
            )

        result = self._run(
            store,
            generator=generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(calls), 3)
        self.assertIn("只输出以下学生", str(calls[2].get("chat_request", {}).get("messages") or ""))
        persisted = json.loads(store.persist_calls[0]["response_text"])
        self.assertEqual(
            {int(item["student_id"]) for item in persisted["items"]},
            {1, 2},
        )

    def test_fallback_request_uses_main_credentials_when_only_model_set(self):
        config = {
            "class_commentary_fallback_model": "fb-model",
            "class_commentary_openai_api_key": "main-key",
            "class_commentary_openai_base_url": "https://main.example",
            "class_commentary_openai_headers": "",
        }
        fallback = _fallback_generation_request(
            {"model_provider": "openai"},
            config,
        )
        self.assertEqual(
            fallback,
            ("openai", "fb-model", "main-key", "https://main.example", ""),
        )
        self.assertIsNone(
            _fallback_generation_request(
                {"model_provider": "openai"},
                {"class_commentary_fallback_model": "fb-model"},
            )
        )
        self.assertIsNone(
            _fallback_generation_request(
                {"model_provider": "openai"},
                {
                    "class_commentary_fallback_model": "",
                    "class_commentary_openai_api_key": "k",
                    "class_commentary_openai_base_url": "b",
                },
            )
        )

    def test_model_fallback_recovers_coverage_after_chain_exhausts(self):
        store = FakeBatchGenerationStore()
        store.generation["attending_roster_snapshot_json"] = json.dumps(
            [
                {"student_id": 1, "student_name": "甲"},
                {"student_id": 2, "student_name": "乙"},
            ]
        )
        main_calls = []

        def generator(**kwargs):
            main_calls.append(copy.deepcopy(kwargs))
            return (
                '{"schema_version":"class_commentary.student_feedback.v1",'
                '"items":[{"student_id":1,"feedback_text":"甲不错"}]}',
                copy.deepcopy(self.usage),
            )

        fallback_calls = []

        def fake_fallback(*_args, **_kwargs):
            fallback_calls.append(copy.deepcopy(_kwargs))
            return (
                '{"schema_version":"class_commentary.student_feedback.v1",'
                '"items":[{"student_id":2,"feedback_text":"乙由备用模型补上"}]}',
                {
                    "provider": "openai",
                    "model": "fb-model",
                    "input_tokens": 10,
                    "output_tokens": 10,
                },
            )

        runtime_config = {
            "class_commentary_batch_generation_timeout": 120,
            "class_commentary_fallback_provider": "openai",
            "class_commentary_fallback_model": "fb-model",
            "class_commentary_fallback_openai_api_key": "fb-key",
            "class_commentary_fallback_openai_base_url": "https://fb.example",
            "class_commentary_fallback_openai_headers": "",
        }
        with patch(
            "class_commentary_batch_generation_jobs.ai_processor."
            "generate_class_commentary_feedback",
            side_effect=fake_fallback,
        ) as fallback_generate:
            result = process_class_commentary_batch_generation(
                store.generation["id"],
                store=store,
                runtime_config=runtime_config,
                claim_owner="worker-a",
                generator=generator,
                charge_finalizer=store.finalize_charge,
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(main_calls), 3)
        self.assertEqual(len(fallback_calls), 1)
        self.assertEqual(fallback_calls[0]["model"], "fb-model")
        self.assertEqual(fallback_calls[0]["openai_api_key"], "fb-key")
        self.assertEqual(fallback_calls[0]["openai_base_url"], "https://fb.example")
        fallback_messages = str(
            fallback_calls[0].get("chat_request", {}).get("messages") or ""
        )
        self.assertIn("只输出以下学生", fallback_messages)
        self.assertIn("2", fallback_messages)
        persisted = json.loads(store.persist_calls[0]["response_text"])
        self.assertEqual(
            {int(item["student_id"]) for item in persisted["items"]},
            {1, 2},
        )
        self.assertIn(
            "乙由备用模型补上",
            store.persist_calls[0]["response_text"],
        )

    def test_provider_failure_retries_once_with_fallback_model(self):
        store = FakeBatchGenerationStore()

        def failing_generator(**_kwargs):
            raise ValueError("boom")

        fallback_calls = []

        def fake_fallback(*_args, **_kwargs):
            fallback_calls.append(copy.deepcopy(_kwargs))
            return self._provider_response()

        runtime_config = {
            "class_commentary_batch_generation_timeout": 120,
            "class_commentary_fallback_provider": "openai",
            "class_commentary_fallback_model": "fb-model",
            "class_commentary_fallback_openai_api_key": "fb-key",
            "class_commentary_fallback_openai_base_url": "https://fb.example",
            "class_commentary_fallback_openai_headers": "",
        }
        with patch(
            "class_commentary_batch_generation_jobs.ai_processor."
            "generate_class_commentary_feedback",
            side_effect=fake_fallback,
        ):
            result = process_class_commentary_batch_generation(
                store.generation["id"],
                store=store,
                runtime_config=runtime_config,
                claim_owner="worker-a",
                generator=failing_generator,
                charge_finalizer=store.finalize_charge,
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(fallback_calls), 1)
        self.assertEqual(fallback_calls[0]["model"], "fb-model")
        self.assertEqual(store.terminal_failure_calls, [])

    def test_provider_failure_without_fallback_still_fails_closed(self):
        store = FakeBatchGenerationStore()

        def failing_generator(**_kwargs):
            raise ValueError("boom")

        result = self._run(
            store,
            generator=failing_generator,
            charge_finalizer=store.finalize_charge,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(store.terminal_failure_calls, ["provider_request_failed"])


if __name__ == "__main__":
    unittest.main()
